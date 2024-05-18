# from moviepy.editor import *
# import re
# import os

# # Create directory if it doesn't exist
# output_directory = 'nouran2'
# if not os.path.exists(output_directory):
#     os.makedirs(output_directory)

# audio = AudioFileClip("nouran2.mp3")

# with open('nouran2.txt', 'r', encoding='utf-8') as file:
#     lines = file.readlines()

#     # Initialize variables
#     line_number = 0
#     i = 0
#     y = 0

#     # Loop through the lines of the file
#     while line_number + 2 < len(lines):
#         if y >= 607:
#             # Parse the time format and extract the numerical values
#             try:
#                 time_x = lines[line_number].strip().split(':')
#                 time_y = lines[line_number + 2].strip().split(':')

#                 # Convert the minutes and seconds to integers and calculate start_time and end_time in milliseconds
#                 start_time = int(time_x[0]) * 60 * 1000 + int(time_x[1]) * 1000
#                 end_time = int(time_y[0]) * 60 * 1000 + int(time_y[1]) * 1000

#                 # Extract the segment
#                 segment = audio.subclip(start_time / 1000, end_time / 1000)

#                 # Save the segment to a new file
#                 i += 1
#                 output_path = os.path.join(output_directory, f"{i}.mp3")
#                 segment.write_audiofile(output_path, codec="mp3")

#                 # Move to the next set of odd lines
#                 line_number += 2
#             except ValueError:
#                 # Skip this pair of lines if unable to parse the timestamp
#                 line_number += 2
#         y = y + 1

# print("Processing completed.")

# #--------------------------------------------------------------------------------------------------------------------------------------------------

# leave the text file without arkam el sawani 

import re

with open('nouran2.txt', 'r', encoding='utf-8') as file:
    lines = file.readlines()

    # Initialize an empty list to store the cleaned lines
    cleaned_lines = []

    # Loop through the lines of the file
    for line in lines:
        # Use regular expression to remove the timestamp numbers
        cleaned_line = re.sub(r'^\d+:\d+\s*', '', line)
        cleaned_lines.append(cleaned_line)

# Write the cleaned lines back to the file
with open('nouran2.txt', 'w', encoding='utf-8') as file:
    file.writelines(cleaned_lines)
