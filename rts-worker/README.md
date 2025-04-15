# Worker for Leica Robotic Total Stations</h1>

This is a worker for Leica Robotic Total Stations. It is designed to run on a Raspberry Pi and is able to connect to a Leica Robotic Total Station via GeoCOM and control it. It fetches available jobs from the RTS API and executes them. If a GPS receiver is connected, the system time can be synchronized with GPS time.

## Installation

Installation is recommended via Docker. The following instructions assume that you have a Raspberry Pi with Docker installed.

1. Clone the repository:

```bash
git clone https://github.com/Engineering-Geodesy-Bonn/rts-network
```

2. Change into the repository directory:

```bash
cd rts-worker
```

3. Adjust the configuration in the `.env` file:

```text
API_HOST=<fill in the host of the RTS API>
API_PORT=<fill in the port of the RTS API>
```

4. Build and run the Docker container:

```bash
docker-compose up -d
```

You can run multiple workers depending on the available USB ports and the number of connected total stations.

```bash
docker-compose up -d --scale worker=3
```

## Custom Workers

The behavior of the worker can be customized by creating a custom task mapping and passing it to the Worker class at initialization. The custom task mapping must be a dictionary with RTSJobType as key and a function as value. The function must accept a single argument, which is of type RTSJobResponse. The function should return None. The Worker class fetches available jobs, sets an available job to running and runs the task. All other communication, e.g. if the task is successful or not, should be done via the RTS API within the task function.

By defining a custom task mapping, the worker can be extended to support total stations from other manufacturers or to support additional tasks. However, the tracking settings managed by the API are currently tailored to Leica total stations. A workaround would be to define custom settings in the task function without using the API.


## GPS Time Synchronization (Raspberry Pi)

In this section, the automatic synchronization of the system clock with GPS time is configured. It may work for other devices similiar to the Raspberry Pi, but was only tested on Raspberry Pi 3 and 4.
The following instructions assume that you have connected a (u-blox) GNSS receiver via usb and its PPS pulse cable to GPIO Pin 4 and Ground to Pin 9.

Install required packages:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install pps-tools gpsd gpsd-clients python3-gps chrony
```

Configure gpsd:

```bash
sudo nano /etc/default/gpsd
```

Paste:

```bash
# Devices gpsd should collect to at boot time.
# They need to be read/writeable, either by user gpsd or the group dialout.
DEVICES="/dev/ACM0 /dev/pps0"

# Other options you want to pass to gpsd
GPSD_OPTIONS="-n"

# Automatically hot add/remove USB GPS devices via gpsdctl
USBAUTO="true"

# Start the gpsd daemon automatically at boot time
START_DAEMON="true"

# Use USB hotplugging to add new USB devices automatically to the daemon
USBAUTO="true"
```

Edit /boot/config.txt and add these lines:

```bash
dtoverlay=pps-gpio,gpiopin=4
enable_uart=1
```

This assumes you connected the pps-pulse cable to GPIO Pin 4 (Pin 7).

Add pps-gpio to /etc/modules:

```bash
sudo bash -c "echo 'pps-gpio' >> /etc/modules"
```

Reboot:

```bash
sudo reboot now
```

Wait until GPS has a solution:

```bash
gpsmon
```

or

```bash
cgps
```

Test PPS-Puls using:

```bash
sudo ppstest /dev/pps0
```

The output should be something like (Only if GPS fix is available!):

```bash
trying PPS source "/dev/pps0"
found PPS source "/dev/pps0"
ok, found 1 source(s), now start fetching data...
source 0 - assert 1642074267.000000251, sequence: 204 - clear  0.000000000, sequence: 0
source 0 - assert 1642074268.000001942, sequence: 205 - clear  0.000000000, sequence: 0
source 0 - assert 1642074269.000001707, sequence: 206 - clear  0.000000000, sequence: 0
source 0 - assert 1642074270.000001316, sequence: 207 - clear  0.000000000, sequence: 0
source 0 - assert 1642074271.000001289, sequence: 208 - clear  0.000000000, sequence: 0 
```

Edit the chrony configuration file:

```bash
sudo nano /etc/chrony/chrony.conf
```

Add:

```bash
refclock SHM 0 refid NMEA
refclock PPS /dev/pps0 refid PPS lock NMEA
```

Restart chrony:

```bash
sudo systemctl restart chrony
```

Check if chrony is using NMEA Time + PPS

```bash
chronyc sources -v
```

Output:

```bash
.-- Source mode  '^' = server, '=' = peer, '#' = local clock.
/ .- Source state '*' = current best, '+' = combined, '-' = not combined,
| /             'x' = may be in error, '~' = too variable, '?' = unusable.
||                                                 .- xxxx [ yyyy ] +/- zzzz
||      Reachability register (octal) -.           |  xxxx = adjusted offset,
||      Log2(Polling interval) --.      |          |  yyyy = measured offset,
||                                \     |          |  zzzz = estimated error.
||                                 |    |           \
MS Name/IP address         Stratum Poll Reach LastRx Last sample
===============================================================================
#* NMEA                          0   4   377    13   +144ns[ +273ns] +/-  312ns
#+ PPS                           0   4   377    13   +144ns[ +144ns] +/-  312ns
^? i.ntpns.org                   0   8     0     -     +0ns[   +0ns] +/-    0ns
^? server1.sim720.co.uk          2   7     1    23   +593us[ +593us] +/-   43ms
^? ntpdfw1.ntppool.net           0   8     0     -     +0ns[   +0ns] +/-    0ns
^? 104.248.145.172               0   8     0     -     +0ns[   +0ns] +/-    0ns
^? ntpcgn1.ntppool.net           0   8     0     -     +0ns[   +0ns] +/-    0ns
^? ntpsjc2.ntppool.net           0   8     0     -     +0ns[   +0ns] +/-    0ns
^? ntpnrt1.ntppool.net           0   8     0     -     +0ns[   +0ns] +/-    0ns
^? ntpnyc1.ntppool.net           0   8     0     -     +0ns[   +0ns] +/-    0ns
```

See tracking performance:

```bash
sudo chronyc tracking
```

```bash
Output:

        Reference ID    : 4E4D4541 (NMEA)
        Stratum         : 1
        Ref time (UTC)  : Thu Jan 13 11:48:55 2022
        System time     : 0.000000066 seconds fast of NTP time
        Last offset     : +0.000000076 seconds
        RMS offset      : 0.000000352 seconds
        Frequency       : 5.559 ppm fast
        Residual freq   : +0.000 ppm
        Skew            : 0.009 ppm
        Root delay      : 0.000000001 seconds
        Root dispersion : 0.000015253 seconds
        Update interval : 16.0 seconds
        Leap status     : Normal
```


