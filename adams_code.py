#!/usr/bin/python
# snakeoil.py

import socket
import sys
import getopt
import os
import time

PI = 3.14159265359
data_size = 2**17

# ============================================================
# OPTIONS
# ============================================================

ophelp = 'Options:\n'
ophelp += ' --host, -H <host>    TORCS server host. [localhost]\n'
ophelp += ' --port, -p <port>    TORCS port. [3001]\n'
ophelp += ' --id, -i <id>        ID for server. [SCR]\n'
ophelp += ' --steps, -m <#>      Maximum simulation steps. [100000]\n'
ophelp += ' --episodes, -e <#>   Maximum learning episodes. [1]\n'
ophelp += ' --track, -t <track>  Your name for this track. [unknown]\n'
ophelp += ' --stage, -s <#>      0=warm up, 1=qualifying, 2=race. [3]\n'
ophelp += ' --debug, -d          Output full telemetry.\n'
ophelp += ' --help, -h           Show this help.\n'
ophelp += ' --version, -v        Show current version.'

usage = 'Usage: %s [ophelp [optargs]] \n' % sys.argv[0]
usage = usage + ophelp
version = "20130505-2"


def clip(v, lo, hi):
    if v < lo:
        return lo
    elif v > hi:
        return hi
    else:
        return v


def bargraph(x, mn, mx, w, c='X'):
    if not w:
        return ''
    if x < mn:
        x = mn
    if x > mx:
        x = mx
    tx = mx - mn
    if tx <= 0:
        return 'backwards'
    upw = tx / float(w)
    if upw <= 0:
        return 'what?'
    negpu, pospu, negnonpu, posnonpu = 0, 0, 0, 0
    if mn < 0:
        if x < 0:
            negpu = -x + min(0, mx)
            negnonpu = -mn + x
        else:
            negnonpu = -mn + min(0, mx)
    if mx > 0:
        if x > 0:
            pospu = x - max(0, mn)
            posnonpu = mx - x
        else:
            posnonpu = mx - max(0, mn)
    nnc = int(negnonpu / upw) * '-'
    npc = int(negpu / upw) * c
    ppc = int(pospu / upw) * c
    pnc = int(posnonpu / upw) * '_'
    return '[%s]' % (nnc + npc + ppc + pnc)


# ============================================================
# CLIENT
# ============================================================

class Client():

    # BUG FIX: was `_init_` (single underscores) — Python never called it,
    # so every attribute (self.host, self.S, self.R, etc.) didn't exist.
    # The constructor MUST be `__init__` (double underscores).
    def __init__(self, H=None, p=None, i=None, e=None,
                 t=None, s=None, d=None, vision=False):

        self.vision = vision

        self.host = 'localhost'
        self.port = 3001
        self.sid = 'SCR'
        self.maxEpisodes = 1
        self.trackname = 'unknown'
        self.stage = 3
        self.debug = False
        self.maxSteps = 100000

        self.parse_the_command_line()

        if H:
            self.host = H
        if p:
            self.port = p
        if i:
            self.sid = i
        if e:
            self.maxEpisodes = e
        if t:
            self.trackname = t
        if s:
            self.stage = s
        if d:
            self.debug = d

        self.S = ServerState()
        self.R = DriverAction()

        # Lap tracking
        self.lap_number = 1
        self.last_dist_from_start = 0

        self.setup_connection()

    # --------------------------------------------------------
    # CONNECTION
    # --------------------------------------------------------

    def setup_connection(self):

        try:
            self.so = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error:
            print('Error: Could not create socket...')
            sys.exit(-1)

        self.so.settimeout(1)
        n_fail = 5

        while True:

            a = "-45 -19 -12 -7 -4 -2.5 -1.7 -1 -.5 0 .5 1 1.7 2.5 4 7 12 19 45"
            initmsg = '%s(init %s)' % (self.sid, a)

            try:
                self.so.sendto(initmsg.encode(), (self.host, self.port))
            except socket.error:
                sys.exit(-1)

            sockdata = str()

            try:
                sockdata, addr = self.so.recvfrom(data_size)
                sockdata = sockdata.decode('utf-8')

            except socket.error:
                print("Waiting for server on %d............" % self.port)
                print("Count Down : " + str(n_fail))

                if n_fail < 0:
                    print("relaunch torcs")
                    os.system('pkill torcs')
                    time.sleep(1.0)
                    if self.vision is False:
                        os.system('torcs -nofuel -nodamage -nolaptime &')
                    else:
                        os.system('torcs -nofuel -nodamage -nolaptime -vision &')
                    time.sleep(1.0)
                    os.system('sh autostart.sh')
                    n_fail = 5

                n_fail -= 1

            # BUG FIX: was `'**identified**'` (double stars).
            # The real TORCS handshake string is `'***identified***'` (triple stars).
            # With the wrong string the while-loop never breaks — client hangs forever.
            identify = '***identified***'

            if identify in sockdata:
                print("Client connected on %d.............." % self.port)
                break

    # --------------------------------------------------------
    # COMMAND LINE
    # --------------------------------------------------------

    def parse_the_command_line(self):

        try:
            opts, args = getopt.getopt(
                sys.argv[1:], 'H:p:i:m:e:t:s:dhv',
                ['host=', 'port=', 'id=', 'steps=', 'episodes=',
                 'track=', 'stage=', 'debug', 'help', 'version'])
        except getopt.error as why:
            print('getopt error: %s\n%s' % (why, usage))
            sys.exit(-1)

        try:
            for opt in opts:
                if opt[0] == '-h' or opt[0] == '--help':
                    print(usage)
                    sys.exit(0)
                if opt[0] == '-d' or opt[0] == '--debug':
                    self.debug = True
                if opt[0] == '-H' or opt[0] == '--host':
                    self.host = opt[1]
                if opt[0] == '-i' or opt[0] == '--id':
                    self.sid = opt[1]
                if opt[0] == '-t' or opt[0] == '--track':
                    self.trackname = opt[1]
                if opt[0] == '-s' or opt[0] == '--stage':
                    self.stage = int(opt[1])
                if opt[0] == '-p' or opt[0] == '--port':
                    self.port = int(opt[1])
                if opt[0] == '-e' or opt[0] == '--episodes':
                    self.maxEpisodes = int(opt[1])
                if opt[0] == '-m' or opt[0] == '--steps':
                    self.maxSteps = int(opt[1])
                if opt[0] == '-v' or opt[0] == '--version':
                    print('%s %s' % (sys.argv[0], version))
                    sys.exit(0)
        except ValueError as why:
            print('Bad parameter \'%s\' for option %s: %s\n%s'
                  % (opt[1], opt[0], why, usage))
            sys.exit(-1)

        if len(args) > 0:
            print('Superflous input? %s\n%s' % (', '.join(args), usage))
            sys.exit(-1)

    # --------------------------------------------------------
    # RECEIVE SERVER DATA
    # --------------------------------------------------------

    def get_servers_input(self):

        if not self.so:
            return

        sockdata = str()

        while True:

            try:
                sockdata, addr = self.so.recvfrom(data_size)
                sockdata = sockdata.decode('utf-8')
            except socket.error:
                print('.', end=' ')

            # BUG FIX: same triple-star strings as above
            if '***identified***' in sockdata:
                print("Client connected on %d.............." % self.port)
                continue

            elif '***shutdown***' in sockdata:
                print(("Server has stopped the race on %d. You were in %d place.")
                      % (self.port, self.S.d['racePos']))
                self.shutdown()
                return

            elif '***restart***' in sockdata:
                print("Server has restarted the race on %d." % self.port)
                self.shutdown()
                return

            elif not sockdata:
                continue

            else:
                self.S.parse_server_str(sockdata)
                if self.debug:
                    sys.stderr.write("\x1b[2J\x1b[H")
                    print(self.S)
                break

    # --------------------------------------------------------
    # SEND RESPONSE
    # --------------------------------------------------------

    def respond_to_server(self):

        if not self.so:
            return

        try:
            message = repr(self.R)
            self.so.sendto(message.encode(), (self.host, self.port))
        except socket.error as emsg:
            print("Error sending to server: %s Message %s"
                  % (emsg[1], str(emsg[0])))
            sys.exit(-1)

        if self.debug:
            print(self.R.fancyout())

    # --------------------------------------------------------
    # SHUTDOWN
    # --------------------------------------------------------

    def shutdown(self):

        if not self.so:
            return

        print("Race terminated or %d steps elapsed. Shutting down %d."
              % (self.maxSteps, self.port))

        self.so.close()
        self.so = None


# ============================================================
# SERVER STATE
# ============================================================

class ServerState():

    # BUG FIX: was `_init_` — must be `__init__`
    def __init__(self):
        self.servstr = str()
        self.d = dict()

    def parse_server_str(self, server_string):

        self.servstr = server_string.strip()[:-1]

        sslisted = (
            self.servstr
            .strip()
            .lstrip('(')
            .rstrip(')')
            .split(')(')
        )

        for i in sslisted:
            w = i.split(' ')
            self.d[w[0]] = destringify(w[1:])

    # BUG FIX: was `_repr_` — must be `__repr__`
    def __repr__(self):
        return self.fancyout()

    def fancyout(self):

        out = str()

        sensors = [
            'stucktimer', 'fuel', 'distRaced', 'distFromStart',
            'opponents', 'wheelSpinVel', 'z', 'speedZ', 'speedY',
            'speedX', 'targetSpeed', 'rpm', 'skid', 'slip',
            'track', 'trackPos', 'angle', 'damage'
        ]

        for k in sensors:

            if k not in self.d:
                continue

            if type(self.d.get(k)) is list:

                if k == 'track':
                    raw_tsens = ['%.1f' % x for x in self.d['track']]
                    strout = (' '.join(raw_tsens[:9]) + '_'
                              + raw_tsens[9] + '_'
                              + ' '.join(raw_tsens[10:]))

                elif k == 'opponents':
                    strout = str()
                    for osensor in self.d['opponents']:
                        if   osensor > 190: oc = '_'
                        elif osensor > 90:  oc = '.'
                        elif osensor > 39:  oc = chr(int(osensor / 2) + 97 - 19)
                        elif osensor > 13:  oc = chr(int(osensor) + 65 - 13)
                        elif osensor > 3:   oc = chr(int(osensor) + 48 - 3)
                        else:               oc = '?'
                        strout += oc
                    strout = ' -> ' + strout[:18] + ' ' + strout[18:] + ' <-'

                else:
                    strout = ', '.join([str(i) for i in self.d[k]])

            else:

                if k == 'speedX':
                    cx = 'R' if self.d[k] < 0 else 'X'
                    strout = '%6.1f %s' % (
                        self.d[k], bargraph(self.d[k], -30, 300, 50, cx))

                elif k == 'trackPos':
                    cx = '>' if self.d[k] < 0 else '<'
                    strout = '%6.3f %s' % (
                        self.d[k], bargraph(self.d[k] * -1, -1, 1, 50, cx))

                else:
                    strout = str(self.d[k])

            out += "%s: %s\n" % (k, strout)

        return out


# ============================================================
# DRIVER ACTION
# ============================================================

class DriverAction():

    # BUG FIX: was `_init_` — must be `__init__`
    def __init__(self):

        self.actionstr = str()

        self.d = {
            'accel':  0.2,
            'brake':  0,
            'clutch': 0,
            'gear':   1,
            'steer':  0,
            'focus':  [-90, -45, 0, 45, 90],
            'meta':   0
        }

    def clip_to_limits(self):

        self.d['steer']  = clip(self.d['steer'],  -1, 1)
        self.d['brake']  = clip(self.d['brake'],   0, 1)
        self.d['accel']  = clip(self.d['accel'],   0, 1)
        self.d['clutch'] = clip(self.d['clutch'],  0, 1)

        if self.d['gear'] not in [-1, 0, 1, 2, 3, 4, 5, 6]:
            self.d['gear'] = 0

        if self.d['meta'] not in [0, 1]:
            self.d['meta'] = 0

        if (type(self.d['focus']) is not list
                or min(self.d['focus']) < -180
                or max(self.d['focus']) > 180):
            self.d['focus'] = 0

    # BUG FIX: was `_repr_` — must be `__repr__`
    def __repr__(self):

        self.clip_to_limits()

        out = str()

        for k in self.d:
            out += '(' + k + ' '
            v = self.d[k]
            if type(v) is not list:
                out += '%.3f' % v
            else:
                out += ' '.join([str(x) for x in v])
            out += ')'

        return out

    def fancyout(self):

        out = str()
        od = self.d.copy()
        od.pop('gear',  '')
        od.pop('meta',  '')
        od.pop('focus', '')

        for k in sorted(od):
            if k in ('clutch', 'brake', 'accel'):
                strout = '%6.3f %s' % (
                    od[k], bargraph(od[k], 0, 1, 50, k[0].upper()))
            elif k == 'steer':
                strout = '%6.3f %s' % (
                    od[k], bargraph(od[k] * -1, -1, 1, 50, 'S'))
            else:
                strout = str(od[k])
            out += "%s: %s\n" % (k, strout)

        return out


# ============================================================
# DESERIALIZE SERVER DATA
# ============================================================

def destringify(s):

    if not s:
        return s

    if type(s) is str:
        try:
            return float(s)
        except ValueError:
            return s

    elif type(s) is list:
        if len(s) < 2:
            return destringify(s[0])
        else:
            return [destringify(i) for i in s]


# ============================================================
# DRIVE FUNCTION
# ============================================================
#
#  Priority order (highest first):
#   1. Sand / off-tarmac recovery   — hard return, nothing overrides
#   2. Steering                     — angle align + cubic edge avoidance
#   3. Look-ahead speed target      — sqrt(forward_dist) * 15, capped at 300
#   4. Lap-number speed cap         — lap 1: 260 km/h   lap 2+: 300 km/h
#   5. Corner / steer speed caps    — graduated hard limits
#   6. Throttle / brake             — proportional to speed gap
#   7. Traction control             — slip-ratio based throttle cut
#   8. ABS                          — halve brake when wheels lock
#   9. RPM-based gear changes       — upshift 8000, downshift 4000
#
# ============================================================

def drive_example(c):

    S = c.S.d
    R = c.R.d

    # --------------------------------------------------------
    # LAP DETECTION
    # --------------------------------------------------------

    dist_from_start = S.get('distFromStart', 0)

    # distFromStart drops sharply when crossing the start line
    if (c.last_dist_from_start > 100
            and dist_from_start < c.last_dist_from_start - 100):
        c.lap_number += 1
        print("\n========== LAP %d STARTED ==========\n" % c.lap_number)

    c.last_dist_from_start = dist_from_start

    # --------------------------------------------------------
    # SENSOR VALUES
    # --------------------------------------------------------

    angle     = S.get('angle',         0.0)
    track_pos = S.get('trackPos',       0.0)   # 0=centre ±1=edge >±1=off road
    speed     = S.get('speedX',         0.0)
    damage    = S.get('damage',         0.0)
    rpm       = S.get('rpm',            0.0)
    gear      = int(S.get('gear',         1))
    track     = S.get('track',   [100.0]*19)
    wv        = S.get('wheelSpinVel', [0.0]*4)

    # --------------------------------------------------------
    # LAYER 1 — SAND / OFF-TARMAC RECOVERY  (hard return)
    # --------------------------------------------------------
    # trackPos > ±1.0 means the car is on sand or grass.
    # Brake hard, steer back, nothing else runs.

    if abs(track_pos) > 1.0:
        R['steer'] = clip(-track_pos * 1.0, -1.0, 1.0)
        R['brake'] = 0.7
        R['accel'] = 0.0
        R['gear']  = 1 if speed >= 0 else -1
        return

    # --------------------------------------------------------
    # LAYER 2 — STEERING
    # --------------------------------------------------------

    # 2a. Align body with track axis
    steer_angle = angle * 10.0 / PI

    # 2b. Cubic centering — soft in the middle, full-lock near the edge
    #     track_pos=0.5 → 0.5³*2.5=0.31   track_pos=0.9 → 0.9³*2.5=1.82→1.0
    edge_urgency = track_pos ** 3
    steer_center = -edge_urgency * 2.5

    # 2c. Sensor-based cornering assist: steer toward the wider side
    if len(track) >= 19:
        left_avg  = sum(track[0:9])  / 9.0
        right_avg = sum(track[10:19]) / 9.0
        total     = left_avg + right_avg
        if total > 1.0:
            steer_center += ((right_avg - left_avg) / total) * 0.30

    # 2d. Reduce steering gain at very high speed to prevent oscillation
    steer_raw = steer_angle + steer_center
    if speed > 200:
        steer_raw *= 0.85
    if speed > 250:
        steer_raw *= 0.80

    R['steer'] = clip(steer_raw, -1.0, 1.0)

    # --------------------------------------------------------
    # LAYER 3 — LOOK-AHEAD SPEED TARGET
    # --------------------------------------------------------
    # Sensor index → bearing:
    #  0=-45° 1=-19° 2=-12° 3=-7° 4=-4° 5=-2.5° 6=-1.7°
    #  7=-1°  8=-0.5° 9=0°  10=+0.5° 11=+1° 12=+1.7° 13=+2.5°
    #  14=+4° 15=+7° 16=+12° 17=+19° 18=+45°

    straight_dist = min(track[7], track[8], track[9], track[10], track[11])
    wide_dist     = min(track[6:14])
    look_ahead    = min(straight_dist, wide_dist * 0.8)

    # sqrt curve: 200 m → 212 km/h | 80 m → 134 km/h | 30 m → 82 km/h
    target_speed = clip((look_ahead ** 0.5) * 15.0, 20.0, 300.0)

    # --------------------------------------------------------
    # LAYER 4 — LAP-NUMBER CAP
    # --------------------------------------------------------

    lap_cap = 300.0 if c.lap_number >= 2 else 260.0
    target_speed = min(target_speed, lap_cap)

    # --------------------------------------------------------
    # LAYER 5 — CORNER / STEER / DAMAGE SPEED CAPS
    # --------------------------------------------------------

    steer_abs = abs(R['steer'])

    # Steer-based graduated cap
    if steer_abs > 0.80:
        target_speed = min(target_speed, 120.0)
    elif steer_abs > 0.60:
        target_speed = min(target_speed, 150.0)
    elif steer_abs > 0.40:
        target_speed = min(target_speed, 190.0)
    elif steer_abs > 0.20:
        target_speed = min(target_speed, 230.0)

    # Edge-proximity speed cut — give steering time to work
    edge_margin = abs(track_pos)
    if edge_margin > 0.60:
        target_speed *= max(1.0 - (edge_margin - 0.60) * 1.8, 0.1)
        target_speed  = max(target_speed, 20.0)

    # Damage-based conservative cap
    if damage > 300:
        target_speed = min(target_speed, 100.0)
    elif damage > 100:
        target_speed = min(target_speed, 140.0)
    elif damage > 0:
        target_speed = min(target_speed, 180.0)

    target_speed = max(target_speed, 20.0)

    # --------------------------------------------------------
    # LAYER 6 — THROTTLE / BRAKE
    # --------------------------------------------------------

    speed_error = target_speed - speed

    if speed < 5.0:
        # Launch: full throttle from standstill
        R['accel'] = 1.0
        R['brake'] = 0.0
    elif speed_error > 25:
        R['accel'] = 1.0
        R['brake'] = 0.0
    elif speed_error > 10:
        R['accel'] = 0.75
        R['brake'] = 0.0
    elif speed_error > 0:
        R['accel'] = 0.45
        R['brake'] = 0.0
    elif speed_error > -15:
        # Slightly over target — coast with a tiny brake touch
        R['accel'] = 0.0
        R['brake'] = 0.05
    else:
        R['accel'] = 0.0
        R['brake'] = clip((-speed_error) / 60.0, 0.0, 1.0)

    # --------------------------------------------------------
    # LAYER 7 — TRACTION CONTROL (slip ratio)
    # --------------------------------------------------------
    # Use slip ratio (relative) rather than raw delta (absolute)
    # so the threshold is correct at all speeds.

    if len(wv) >= 4:
        front_spin = (wv[0] + wv[1]) / 2.0 + 0.001   # avoid /0
        rear_spin  = (wv[2] + wv[3]) / 2.0
        slip_ratio = (rear_spin - front_spin) / front_spin
        if slip_ratio > 0.15:
            R['accel'] = max(R['accel'] - 0.4 * (slip_ratio - 0.15), 0.0)

    # --------------------------------------------------------
    # LAYER 8 — ABS (anti-lock braking)
    # --------------------------------------------------------
    # If the front wheels are locking under braking, halve brake pressure.

    if len(wv) >= 4:
        front_spin_abs = (wv[0] + wv[1]) / 2.0 + 0.001
        if R['brake'] > 0 and speed > 10.0 and front_spin_abs < speed * 0.05:
            R['brake'] *= 0.5

    # --------------------------------------------------------
    # LAYER 9 — RPM-BASED GEAR CHANGES
    # --------------------------------------------------------
    # BUG FIX: the original reset gear=1 every step then re-evaluated.
    # This causes a momentary gear-1 command every tick even at 200 km/h.
    # Use RPM thresholds from the current gear instead.

    if gear < 1:
        gear = 1
    if rpm > 8000 and gear < 6:
        gear += 1
    elif rpm < 4000 and gear > 1:
        gear -= 1
    R['gear'] = gear

    # --------------------------------------------------------
    # LAYER 10 — BACKWARDS GUARD
    # --------------------------------------------------------

    if speed < -2.0:
        R['gear']  = -1
        R['accel'] = 0.5
        R['brake'] = 0.0
        R['steer'] = 0.0

    # --------------------------------------------------------
    # FINAL CLIP (safety net)
    # --------------------------------------------------------

    R['accel'] = clip(R['accel'], 0.0, 1.0)
    R['brake'] = clip(R['brake'], 0.0, 1.0)
    R['steer'] = clip(R['steer'], -1.0, 1.0)

    return


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    C = Client()

    for step in range(C.maxSteps, 0, -1):
        C.get_servers_input()
        drive_example(C)
        C.respond_to_server()

    C.shutdown()
