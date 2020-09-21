

import serial
import socket
import time
import threading
import subprocess
import math
from halo import Halo

#low latency (15 fps /!\)
#/usr/local/vigiclient/processdiffvideo -r 15 -i udp://0.0.0.0:11111 -c:v h264_omx -profile:v baseline -b:v 500k -flags:v +global_header -bsf:v dump_extra -f rawvideo udp://127.0.0.1:9999
#high quality
#/usr/local/vigiclient/processdiffvideo -i udp://0.0.0.0:11111 -c:v h264_omx -profile:v baseline -b:v 3M -flags:v +global_header -bsf:v dump_extra -f rawvideo udp://127.0.0.1:9999

#loool !/usr/bin/env pypy

# const values
TELLO_IP = "192.168.10.1" #"127.0.0.1"
TELLO_PORT = 8889
PI_PORT = 8890
PI_LISTENIP = "0.0.0.0"
TRAMESIZE = 17
RESPONSETRAMESIZE = 30
CONNECTCOMMAND = "command"
STREAMONCOMMAND = "streamon"
STREAMOFFCOMMAND = "streamoff"
TAKEOFFCOMMAND = "takeoff"
LANDCOMMAND = "land"
EMERGENCYCOMMAND =  "emergency"
FLIPFCOMMAND =  "flip f"
RCCOMMAND = "rc %s %s %s %s" # leftright, forward/backward, up/down, yaw,
TELLOSTATESTRUCTURE = ["pitch", "roll", "yaw", "vgx", "vgy", "vgz", "templ", "temph", "tof", "h", "bat", "baro", "time", "agx", "agy", "agz", "\r\n"]



payloadSize =  TRAMESIZE - 4 
vigiSerial = serial.Serial("/dev/pts/0", 115200)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
syncTime = time.time()
syncRC = time.time()
syncTelloTime = time.time()
freqRC = 0.0
freqTello = 0

lastTrame = bytearray(payloadSize)
telloStateTrame = [0]*len(TELLOSTATESTRUCTURE) #todo : create class
updatedRC = False # simple hack to match Tello frequency from Vigibot frequency

#hqTranscoder = subprocess.run(["/usr/local/vigiclient/processdiffvideo", "-r", "15", "-i", "udp://0.0.0.0:1111", "-c:v h264_omx", "-profile:v", "baseline", "-b:v", "1M", "-flags:v", "+global_header", "-bsf:v", "dump_extra", "-f", "rawvideo", "udp://127.0.0.1:9999"])


spinner = Halo(text='Starting', spinner='dots')
spinner.start()
warningLogs = ""




class parsedTrame():

    def __init__(self):
        self.yaw = 0
        self.pitch = 0
        self.choixCam = 0
        self.vX = 0
        self.vY = 0
        self.vT= 0
        self.takeOff=  0 
        self.land = 0
        self.videoStream = 0
        self.emergency = 0
        self.flipF = 0

    def update(self, trameData: bytearray()):
            self.freq = "RX : %.0f Hz" % (1/elapsed)
            self.yaw = round(int.from_bytes(trameData[0:2], byteorder='little', signed=True) / 245.75)
            self.pitch = round(int.from_bytes(trameData[2:4], byteorder='little', signed=True) / 100.12)

            self.choixCam = trameData[8]
            self.vX = round(bytetoInt8(trameData[9]) / 1.27)
            self.vY = round(bytetoInt8(trameData[10]) / 1.27)
            self.vT = - round(bytetoInt8(trameData[11]) / 1.27)

            self.takeOff = bool(trameData[12] & 1)
            self.land = bool(trameData[12] & 2)
            # bool(trameData[12] & 4)
            # bool(trameData[12] & 8)
            self.videoStream = bool(trameData[12] & 16)
            self.emergency = bool(trameData[12] & 32)
            self.flipF =  bool(trameData[12] & 64)


parsedT = parsedTrame()


def bytetoInt8(byte):
    if byte > 127:
        return (256-byte) * (-1)
    else:
        return byte


def sendCommandtoTello(command : str):
    command = command
    return sock.sendto(command.encode("utf-8"), (TELLO_IP, TELLO_PORT))


def telloReceiveState():
    global syncTelloTime, freqTello
    sockR = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sockR.bind((PI_LISTENIP, PI_PORT))
    while True:
        data, addr = sockR.recvfrom(1024) # buffer size is 1024 bytes, quite enough for the short tello state trames
        result = data.decode().split(";")
        
        if len(result) == len(TELLOSTATESTRUCTURE):
            for ind, r in  enumerate(result):
                if r.find(TELLOSTATESTRUCTURE[ind]) > -1 and r.find(":") > -1:
                    telloStateTrame[ind] = float(r.split(":")[1])

        newT = time.time()
        freqTello = 1/(newT - syncTelloTime)
        syncTelloTime = newT
        #print(data)

def getTelloStateValue(state :str):
    val = telloStateTrame[TELLOSTATESTRUCTURE.index(state)]
    return val

def clamp(x, minimum, maximum):
   return max(minimum, min(x, maximum))

def scaleToInt8(value, minv, maxv, signed = False):
    clippedVal = clamp(value, minv, maxv)
    result = int(255*clippedVal/(maxv-minv))
    if not signed or result >= 0:
        return result
    else:
        return result + 256




def generateResponseTrame(): # -> bytearray(30):
    responseTrame = bytearray(b'\x00') * RESPONSETRAMESIZE
    # copy original trame 
    responseTrame[4:4 + len(lastTrame)] = lastTrame
    responseTrame[0] = int("0x24", 0)
    responseTrame[1] = int("0x52", 0)
    responseTrame[2] = int("0x20", 0)
    responseTrame[2] = int("0x20", 0)

    # 16 bits values 
    #responseTrame[18] # Voltage (will be updated by Raspberry pi)
    #responseTrame[19] # Percent (will be updated by Raspberry pi)

    # 8 bits values
    responseTrame[16] = lastTrame[8] # recopy choix camera
    responseTrame[17] = lastTrame[9] # recopy v
    responseTrame[18] = lastTrame[10]
    responseTrame[19] = lastTrame[11]
    responseTrame[20] = lastTrame[12] # recopy switches

    # bytes 21 to 24 = overidded by Raspi
    responseTrame[21] # cpu load
    responseTrame[22] # soc temp
    responseTrame[23] # link
    responseTrame[24] # rssi
    responseTrame[25] = scaleToInt8(getTelloStateValue("bat"), 0, 100) #bat
    responseTrame[26] = scaleToInt8(getTelloStateValue("temph"), 0, 100) # VPU temp
    responseTrame[27] = scaleToInt8(getTelloStateValue("tof"), 0, 255) # indoor altitude (tof sensor)
    responseTrame[28] = scaleToInt8( -getTelloStateValue("vgz"), -100, 100, signed=True) # tello V speed
    hSpeed = math.sqrt( getTelloStateValue("vgx")**2 + getTelloStateValue("vgy")**2 ) 
    responseTrame[29] =scaleToInt8(hSpeed, 0, 100) # tello H speed = sqrt(vgx²+vgy²)

    # print(responseTrame.hex())
    vigiSerial.write(responseTrame)
    threading.Timer(1/19.9, generateResponseTrame).start() # return responseTrame # 

generateResponseTrame()


def telloUpdateRC():
    global updatedRC, syncRC, freqRC, warningLogs
    # One time command
    if parsedT.takeOff:
        warningLogs += " Take off command"
        sendCommandtoTello(TAKEOFFCOMMAND)
    if parsedT.land:
        warningLogs += " Land command"
        sendCommandtoTello(LANDCOMMAND)
    if parsedT.flipF:
        warningLogs += " Flip command"
        sendCommandtoTello(FLIPFCOMMAND)
    if parsedT.emergency:
        warningLogs += " Emergency command"
        sendCommandtoTello(EMERGENCYCOMMAND)

    # RC commands : leftright, forward/backward, up/down, yaw,
    #rc = RCCOMMAND % (parsedT.vY, parsedT.pitch, parsedT.vX, parsedT.yaw) # config 1
    rc =  RCCOMMAND % (parsedT.yaw, parsedT.vY, parsedT.pitch, parsedT.vT) # config 2
    # print(rc)
    if not updatedRC:
        sendCommandtoTello(rc)
        newT = time.time()
        freqRC = 1/(newT - syncRC)
        syncRC = newT
    updatedRC = not updatedRC # skip next update

def tellloHandleStreamOnOff():
    sendCommandtoTello(CONNECTCOMMAND)
    
    if parsedT.videoStream:
        sendCommandtoTello(STREAMONCOMMAND)
    else:
        sendCommandtoTello(STREAMOFFCOMMAND)

    threading.Timer(1, tellloHandleStreamOnOff).start()


tellloHandleStreamOnOff()
telloReceiveThread = threading.Thread(target=telloReceiveState)
telloReceiveThread.start()


# main thread is sync on vigibot serial update

while 1 :
    lastByte = vigiSerial.read()
    
    #sync check
    if (lastByte == b'$') :
        currentByte = vigiSerial.read()
        if(currentByte == b'S'):
            #in sync, flush 2 (sync padding) and read trame
            vigiSerial.read(2)
            lastTrame = vigiSerial.read(payloadSize)
            elapsed = (time.time() - syncTime)
            syncTime = time.time()

            trameHex = lastTrame.hex()
            freq = (1/elapsed)

            logs = "Main frequency : %4.1f Hz | Tello telemetry :  %4.1f Hz | Tello commands : %4.1f Hz" % (freq, freqTello, freqRC) + " | " + warningLogs
            warningLogs = ""
            spinner.text = logs
            
            parsedT.update(lastTrame)

            telloUpdateRC()


            
            

