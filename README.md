# Bird-Watcher

A self-hosted web app to be placed on a micro computer (96boards or raspberry-pi). The app will use a connected camera to live-stream a video feed on demand and has the capability to auto-record and save small video snippets when motion (a bird for example) is detected in the designated camera area.

## Getting-Started

### Installing Requirements

On your device make sure to install `ffmpeg` that should be on the PATH and some libraries: `libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev`

#### For Debiam/Ubuntu

simply run `sudo apt-get install ffmpeg libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev`

#### For Alpine Linux

Run `sudo apk install ffmpeg ffmpeg-libavformat ffmpeg-libavcodec ffmpeg-libavdevice ffmpeg-libavutil ffmpeg-libswscale ffmpeg-libswresample ffmpeg-libavfilter`
