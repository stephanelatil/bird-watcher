# Bird-Watcher

A self-hosted web app to be placed on a micro computer (96boards or raspberry-pi). The app will use a connected camera to live-stream a video feed on demand and has the capability to auto-record and save small video snippets when motion (a bird for example) is detected in the designated camera area.

## Getting-Started

### Installing Requirements

On your device make sure to install `ffmpeg` and `libx264` that should be on the PATH.

#### For Debiam/Ubuntu

simply run `sudo apt-get install libx264 ffmpeg`

#### For Alpine Linux

Run `sudo apk install x264-libs ffmpeg`
