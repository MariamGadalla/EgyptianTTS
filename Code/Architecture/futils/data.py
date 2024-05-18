import os
import re
import pandas as pd
import text
import torch
import torchaudio
import numpy as np
from torch.utils.data import Dataset

from futils import read_lines_from_file, progbar
from futils.audio import MelSpectrogram

def text_mel_collate_fn(batch, pad_value=0):
    """
    Args:
        batch: List[(text_ids, mel_spec)]
    Returns:
        text_ids_pad
        input_lengths
        mel_pad
        gate_pad
        output_lengths
    """
    # Sort batch by input sequence length in descending order
    input_lens_sorted, input_sort_ids = torch.sort(
        torch.LongTensor([len(x[0]) for x in batch]),
        dim=0, descending=True)
    max_input_len = input_lens_sorted[0]

    # Ensure that all mel spectrograms have valid dimensions
    for i, item in enumerate(batch):
        if item[1].dim() != 2:
            raise ValueError(f"Invalid mel spectrogram dimension at batch index {i}, got {item[1].dim()}")

    num_mels = batch[0][1].size(0)
    max_target_len = max([x[1].size(1) for x in batch])

    # Initialize padded tensors
    text_ids_pad = torch.LongTensor(len(batch), max_input_len).zero_()
    mel_pad = torch.FloatTensor(len(batch), num_mels, max_target_len).fill_(pad_value)
    gate_pad = torch.FloatTensor(len(batch), max_target_len).zero_()
    output_lengths = torch.LongTensor(len(batch))

    # Populate padded tensors
    for i in range(len(input_sort_ids)):
        text_ids, mel = batch[input_sort_ids[i]][0], batch[input_sort_ids[i]][1]
        text_ids_pad[i, :text_ids.size(0)] = text_ids
        mel_pad[i, :, :mel.size(1)] = mel
        gate_pad[i, mel.size(1)-1:] = 1
        output_lengths[i] = mel.size(1)

    return text_ids_pad, input_lens_sorted, \
        mel_pad, gate_pad, output_lengths


def normalize_pitch(pitch, 
                    mean: float = 130.05478, 
                    std: float = 22.86267):
    zeros = (pitch == 0.0)
    pitch -= mean
    pitch /= std
    pitch[zeros] = 0.0
    return pitch

def remove_silence(energy_per_frame: torch.Tensor, 
                   thresh: float = -10.0):
    keep = energy_per_frame > thresh
    # keep silence at the end
    i = keep.size(0)-1
    while not keep[i] and i > 0:
        keep[i] = True
        i -= 1
    return keep

def make_dataset_from_subdirs(folder_path):
    samples = []
    for root, _, fnames in os.walk(folder_path, followlinks=True):
        for fname in fnames:
            if fname.endswith('.wav'):
                samples.append(os.path.join(root, fname))

    return samples

def _process_line(label_pattern: str, line: str):        
    match = re.search(label_pattern, line)
    if match is None:
        raise Exception(f'no match for line: {line}')

    res_dict = match.groupdict()

    if 'arabic' in res_dict:
        phonemes = text.arabic_to_phonemes(res_dict['arabic'])
    elif 'phonemes' in res_dict:
        phonemes = res_dict['phonemes']
    elif 'buckwalter' in res_dict:
        phonemes = text.buckwalter_to_phonemes(res_dict['buckwalter'])
    
    if 'filename' in res_dict:
        filename = res_dict['filename']
    elif 'filestem' in res_dict:
        filename = f"{res_dict['filestem']}.wav"        

    return phonemes, filename


class ArabDataset(Dataset):
    def __init__(self,
                 csv_file: str,
                 wavpath: str,
                 sr_target: int = 22050
                 ):
        super().__init__()

        self.mel_fn = MelSpectrogram(sample_rate=sr_target, n_mels=80)
        self.wav_path = wavpath
        self.sr_target = sr_target
        self.csv_file = csv_file
        self.data = self._process_csvfile()
    
    def _process_csvfile(self):
        df = pd.read_csv(self.csv_file)

        # Ensure required columns are present
        required_columns = ['index', 'text', 'Diacterized', 'Buckwalter', "Cleaned_Text"]
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
            
        # Process each row to construct the dataset entries
        data_list = []
        for _, row in df.iterrows():
            try:
                # Get text data
                dia_arabic = row['text']
                bw_arabic = row["Buckwalter"]
                eng_arabic = row["Cleaned_Text"]
                filename = f"clip_{row['index']:05}.wav"

                # Tokenize and convert to IDs
                #dia_tokens = text.arabic_to_tokens(dia_arabic)
                #dia_token_ids = text.tokens_to_ids(dia_tokens)

                bw_tokens = text.buckwalter_to_tokens(bw_arabic)
                bw_token_ids = text.tokens_to_ids(bw_tokens)

                #eng_tokens = text.phonemes_to_tokens(eng_arabic)
                #eng_token_ids = text.tokens_to_ids(eng_tokens)

                # Construct file path
                fpath = os.path.join(self.wav_path, filename)
                if not os.path.exists(fpath):
                    print(f"{fpath} does not exist")
                    continue
                
                # Append to data list
                data_list.append((torch.LongTensor(bw_token_ids), fpath))
            except Exception as e:
                print(f"Error processing row: {row}, Error: {str(e)}")
                continue
        
        return data_list

    def _get_mel_from_fpath(self, fpath):
        wave, sr = torchaudio.load(fpath)
        if sr != self.sr_target:
            wave = torchaudio.functional.resample(wave, sr, self.sr_target, 64)

        mel_raw = self.mel_fn(wave)
        mel_log = mel_raw.clamp_min(1e-5).log().squeeze()

        energy_per_frame = mel_log.mean(0)
        mel_log = mel_log[:, remove_silence(energy_per_frame)]

        print(f"Mel spectogram shape for {fpath}: {mel_log.shape}")

        # Ensure the mel spectrogram is 2D
        if mel_log.dim() != 2:
            raise ValueError(f"Mel spectrogram at {fpath} is not 2D")

        return mel_log

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):

        bw_phonemes, fpath = self.data[idx]
        mel_log = self._get_mel_from_fpath(fpath)

        return bw_phonemes, mel_log
    
    def __len__(self):
        return len(self.data)

    

class ArabDataset4FastPitch(Dataset):
    def __init__(self, 
                 txtpath: str = './data/train_phon.txt',
                 wavpath: str = 'G:/data/arabic-speech-corpus/wav_new',                
                 label_pattern: str = '"(?P<filename>.*)" "(?P<phonemes>.*)"',
                 f0_dict_path: str = './data/pitch_dict.pt',
                 f0_mean: float = 130.05478, 
                 f0_std: float = 22.86267,
                 sr_target: int = 22050
                 ):
        super().__init__()
        from models.fastpitch.fastpitch.data_function import BetaBinomialInterpolator

        self.mel_fn = MelSpectrogram()
        self.wav_path = wavpath
        self.label_pattern = label_pattern
        self.sr_target = sr_target

        self.f0_dict = torch.load(f0_dict_path)
        self.f0_mean = f0_mean
        self.f0_std = f0_std
        self.betabinomial_interpolator = BetaBinomialInterpolator()

        self.data = self._process_textfile(txtpath)


    def _process_textfile(self, txtpath: str):
        lines = read_lines_from_file(txtpath)

        phoneme_mel_pitch_list = []

        for l_idx, line in enumerate(progbar(lines)):

            try:
                phonemes, filename = _process_line(
                    self.label_pattern, line)
            except:
                print(f'invalid line {l_idx}: {line}')
                continue

            fpath = os.path.join(self.wav_path, filename)            
            if not os.path.exists(fpath):
                print(f"{fpath} does not exist")
                continue

            try:
                tokens = text.phonemes_to_tokens(phonemes)
                token_ids = text.tokens_to_ids(tokens)
            except:
                print(f'invalid phonemes at line {l_idx}: {line}')
                continue
                    
            wav_name = os.path.basename(fpath)
            pitch_mel = self.f0_dict[wav_name][None]
         
            phoneme_mel_pitch_list.append(
                (torch.LongTensor(token_ids), fpath, pitch_mel))
        
        return phoneme_mel_pitch_list

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):

        phonemes, fpath, pitch_mel = self.data[idx]

        wave, sr = torchaudio.load(fpath)
        if sr != self.sr_target:
            wave = torchaudio.functional.resample(wave, sr, self.sr_target, 64)

        mel_raw = self.mel_fn(wave)
        mel_log = mel_raw.clamp_min(1e-5).log().squeeze()

        keep = remove_silence(mel_log.mean(0))
        mel_log = mel_log[:, keep]
        pitch_mel = normalize_pitch(pitch_mel[:,keep], self.f0_mean, self.f0_std)

        energy = torch.norm(mel_log.float(), dim=0, p=2)
        attn_prior = torch.from_numpy(
            self.betabinomial_interpolator(mel_log.size(1), len(phonemes)))

        speaker = None
        return (phonemes, mel_log, len(phonemes), pitch_mel, 
                energy, speaker, attn_prior,
                fpath)


class DynBatchDataset(ArabDataset4FastPitch):
    def __init__(self, 
                 txtpath: str = './data/train_phon.txt',
                 wavpath: str = 'G:/data/arabic-speech-corpus/wav_new',
                 label_pattern: str = '"(?P<filename>.*)" "(?P<phonemes>.*)"',
                 f0_dict_path: str = './data/pitch_dict.pt',
                 f0_mean: float = 130.05478, 
                 f0_std: float = 22.86267,
                 max_lengths: list[int] = [1000, 1300, 1850, 30000],
                 batch_sizes: list[int] = [10, 8, 6, 4],
                 ):
        
        super().__init__(txtpath=txtpath, wavpath=wavpath,
                         label_pattern=label_pattern,
                         f0_dict_path=f0_dict_path,
                         f0_mean=f0_mean, f0_std=f0_std)

        self.max_lens = [0,] + max_lengths
        self.b_sizes = batch_sizes

        self.id_batches = []
        self.shuffle()

    def shuffle(self):
      
        lens = [x[2].size(1) for x in self.data] # x[2]: pitch

        ids_per_bs = {b: [] for b in self.b_sizes}

        for i, mel_len in enumerate(lens):
            b_idx = next(i for i in range(len(self.max_lens)-1)
                         if self.max_lens[i] <= mel_len < self.max_lens[i+1])
            ids_per_bs[self.b_sizes[b_idx]].append(i)

        id_batches = []

        for bs, ids in ids_per_bs.items():
            np.random.shuffle(ids)
            ids_chnk = [ids[i:i+bs] for i in range(0, len(ids), bs)]
            id_batches += ids_chnk

        self.id_batches = id_batches

    def __len__(self):
        return len(self.id_batches)

    def __getitem__(self, idx):
        batch = [super(DynBatchDataset, self).__getitem__(idx)
                 for idx in self.id_batches[idx]]
        return batch
    