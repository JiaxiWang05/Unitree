# Record 5 s from the G1's built-in mic to mic_test.wav (run on the robot's Jetson, PC2)
import socket, struct, sys, time, wave

LOCAL_IP = sys.argv[1] if len(sys.argv) > 1 else "192.168.123.164"  # PC2's address
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("", 5555))
s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
             struct.pack("=4s4s", socket.inet_aton("239.168.123.161"), socket.inet_aton(LOCAL_IP)))
s.settimeout(2)
w = wave.open("mic_test.wav", "wb")
w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
start = last = time.time()
got, loudest, end = 0, 0, start + 5
while time.time() < end:
    try:
        data = s.recv(65536)
    except socket.timeout:
        if not got:
            sys.exit("No audio at all: put the voice assistant in wake-up mode (L1 + L2)")
        print("Audio stopped after %.1f s" % (last - start))
        break
    last = time.time()
    w.writeframes(data)
    got += len(data)
    loudest = max([loudest] + [abs(v) for v in struct.unpack("<%dh" % (len(data) // 2), data[: len(data) // 2 * 2])])
w.close()
print("got %d bytes, loudest sample %d" % (got, loudest))
if loudest <= 2:
    print("All zeros: the mic is muted. Put the voice assistant in wake-up mode (L1 + L2)")
