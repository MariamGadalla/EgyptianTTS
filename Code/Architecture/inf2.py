from models.tacotron2 import Tacotron2Wave
import torch
import torchaudio

model = Tacotron2Wave('checkpoints/exp_tc2/states.pth')
#model = Tacotron2Wave('pretrained/tacotron2_ar_adv.pth')
device = torch.device('cpu')
model = model.to(device)
model.eval()

# input_text ="kunoto kunoto >ataEoriftF EalaY >am~a EyAlay"
input_text = ">anA Aln~ahAridapu Einody wAHidN waxamosyna sanapF ma$o EAyizo >stnY biSarAHapK >am~A rajaEto ma$o EAyizo >stnY kamAno Ea$ora sinyna"

with torch.no_grad():
    wave = model.tts(
    text_buckw = input_text, # input text
    speed = 1, # speaking speed
    denoise = 0.0001, # HifiGAN denoiser strength
    speaker_id = 0, # speaker id
    batch_size = 8, # batch size for batched inference
    vowelizer = None, # vowelizer model
    return_mel = False # return mel spectrogram?
)

wave = wave.squeeze().cpu().detach().numpy()

# Define the output path
output_path = "output_audio.wav"
sampling_rate = 22050  # Ensure this matches the model's sampling rate

# Save the audio using torchaudio
torchaudio.save(output_path, torch.tensor(wave).unsqueeze(0), sample_rate=sampling_rate)

print(f"Saved the audio file to {output_path}")