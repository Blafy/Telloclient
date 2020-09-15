# Telloclient
A python client to control the DJI/Ryze Tello drone through Vigibot, a low-latency interface for robots.      

## Why ?

The Tello from Ryze Robotics is a fun little quadcopter. While being quite cheap and equipped with brushed motors, it is different from the other quadcopters of its range :
- It has a decent 720p camera with a good stabilization (although it's only software)
- On board there is an Intel VPU, which runs a 'VPS' (Visual positioning system). The chip is so juicy that the drone needs to fly to avoid overheating, but the drone is very stable.
- It also has a precise range sensor and a barometer
- And the most important feature here, Ryze developped a SDK to allow a computer to talk with the drone - getting video, sensors data and sending commands !
So I thought it could be a fun project to develop a relay between the drone and Vigibot, making the drone completely accesible from internet.

## Prerequisites

- I use a Raspberry Pi 3 for this project, but keep in mind that it shows some limitation - the Pi needs to transcode the video stream. A Pi 4 is worth the upgrade here.
- The drone works only in AP mode (the Edu version allows at STA mode but it's limited), so you will need a dedicated WLAN for the drone. For indoor usage, the internal wifi interface of the Pi is enough, but for better performance or outdoor usage I recommand a wifi USB stick with a high-gain antenna (I have a WN722n) or a repeater (the Tello community uses a Xiaomi Repeater 2)
- Another interface for internet link - your home connection through an ethernet cable is perfect.

## How it works 

For now, my code uses the protocol in the official SDK from Ryze. It is simple to implement because it's made of string commands to send through UDP, like ```takeoff```. However, it's not the optimal choice, because the smartphone application uses a different protocol (not documented) with more functionnalities and logs. Some [libraries](https://github.com/hanyazou/TelloPy) uses this retro-engineering phone API to talk with the drone.    

The main thread is sync with vigibot trames coming from serial. A seperate thread takes care of receiving tello "state" packets, a thread send vigibot RX trames and a 1-sesonc timer take care of the streamon/off command.    

The architecture is under developpement and the code is messy, some revisions are coming. However no thread locks are required and the parsing is failproof. 

## Installation 

1. To begin with, you need to create a robot on Vigibot. Use the default config.

2. Install the [Vigibot client]( ) on your Raspi. Make sure the service runs, and follow the instructions to auth the client (robot/password)

3. Clone this repo. You will find the configs for the client (robot.json) and 2 configs to change in the vigibot interface (remote.json and hardware.json)

4. Create a virtual serial interface with socat. A service config file is in the repo. Copy it in `/etc/systemd/system` 

5. Configure your WLAN interface to connect to the drone. (modify `wpa_supplicant.conf`)

6. Run "pip3 install -r requirement.txt" in order to install the dependancies.

7. Finally, turn on your Tello and run `sudo python3 telloclient.py`. Note that sudo is required to write to the virtual interface. 

8. If everythings is alright, you should see the threads frequencies in the console. It should be ~20Hz, ~10Hz and ~10Hz. 