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

## Configuration

| Environment variable | Default | Meaning |
|---|---|---|
| `API_HOST` / `API_PORT` | 192.168.0.101 / 8000 | API server; if unreachable, the local /24 network is scanned |
| `MEASUREMENT_LOG_DIR` | `measurements` | CSV logs and the outbox (shared by all workers of a device) |
| `WORKER_ID` | random | Identity of the worker (shown in the dashboard) |
| `HEARTBEAT_INTERVAL` | 2 | s between health reports |
| `SIM_TARGET` | – | `E,N,H` center of the simulated prism path (shared by simulated stations) |

## Reliability

- **Outbox**: every measurement is committed to `measurements/outbox.db` (SQLite) before anything else and deleted only after the API confirmed that it is stored. If the API or the network is down, the worker keeps measuring and uploads the backlog later. After a crash or reboot the remaining measurements are sent on start; the rows of a worker that stopped are adopted by the other workers of the device after 30 s.
- **CSV log**: additionally, every measurement is appended to `measurements/<job_id>.csv` (columns of the API's CSV download, plus request time and sequence number). It can be uploaded again with `rts-api/scripts/import_csv.py`.
- **Lease**: the worker renews the lease of its job every second. Network problems never stop a measurement; only a stop from the dashboard does.
- **Shutdown**: on SIGTERM/SIGINT (`docker stop`, Ctrl+C) the running measurement is ended cleanly and reported, so its station is free again at once.
- **Serial port**: opened exclusively, so two jobs can never talk to the same instrument.

## Simulated Total Station

A total station configured with the port `sim://<name>` is simulated (25 Hz, prism moving on a circle, drifting instrument clock). Use it to try the system or to test without hardware.

## Health Reporting

Every worker sends a heartbeat to the API every 2 seconds. The API turns it into plain problem messages on the dashboard's **Measure** page (e.g. *Clock is synchronized over the network only*) and shows the state of each Raspberry Pi under **Setup**. A heartbeat contains:

- **Clock synchronization**: `chronyc tracking` and `chronyc sources` of the host (reference clock, offset, estimated error, PPS source). The Docker image contains `chronyc`; thanks to host networking it queries the chrony daemon of the host (`CHRONY_HOST`, default `127.0.0.1`).
- **GNSS receiver**: fix, satellites and DOP from gpsd (`GPSD_HOST`/`GPSD_PORT`, default `127.0.0.1:2947`).
- **Clock comparison with the API**: an NTP-like offset and round trip measurement, used to cross-check that all devices agree on the time.
- **System**: CPU temperature, under-voltage (Raspberry Pi), free disk space, available serial ports.
- **Runtime**: current job, unsent measurements in the outbox and their age, last error, prism lost.

The job type `health_check` (*Instrument check* in the dashboard) reads model, serial number, firmware, battery and temperature of the total station and measures the GeoCOM latency. Tracking jobs report the same information when they start.

## Custom Tasks

Tasks are functions `task(ctx: JobContext) -> None` registered in `rtsworker/tasks.py` (`TASKS`). A task returns normally on success and raises on failure; the worker reports the result. Measuring tasks write measurements with `ctx.sink.put(response)` and end when `ctx.stop` is set. A custom mapping can be passed to `Worker(tasks=...)`.

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


