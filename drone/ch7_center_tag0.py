#!/usr/bin/env python3
"""CH7 -> Offboard -> center on tag 0 and hold over it. Flip back to Position to take over.

Fly in Position mode over tag 0, flip CH7: the aircraft centers on tag 0 and holds.
Flip CH7 back: the hold stands down and the pilot has it. Flip again to re-engage.
"""
import time
import rclpy
from rclpy.node import Node
from dexi_interfaces.srv import FlightCommand, TagNavCommand

TAG = 0
HOLD_CHUNK_S = 30.0

rclpy.init()
node = Node('ch7_center_tag0')
flight = node.create_client(FlightCommand, '/dexi/flight/command')
tagnav = node.create_client(TagNavCommand, '/dexi/tag_nav/command')
for c in (flight, tagnav):
    while not c.wait_for_service(timeout_sec=5.0):
        print(f'waiting for {c.srv_name}', flush=True)

def call(client, req):
    f = client.call_async(req)
    rclpy.spin_until_future_complete(node, f)
    r = f.result()
    print(f'{req.command}: {"ok" if r.success else "FAILED"} {r.message}', flush=True)
    return r.success

def tn(cmd, timeout=0.0, hold_s=0.0):
    q = TagNavCommand.Request(); q.command = cmd; q.tag_id = TAG; q.timeout = float(timeout); q.hold_s = float(hold_s)
    return call(tagnav, q)

fq = FlightCommand.Request(); fq.command = 'start_setpoint_stream'
call(flight, fq)   # heartbeat WITHOUT commanding Offboard, so PX4 will accept the CH7 flip
print('READY: fly over tag 0 in Position, flip CH7 to engage', flush=True)

while rclpy.ok():
    if not tn('wait_for_offboard', timeout=3600.0):
        time.sleep(0.5); continue
    if not tn('center_on_tag', timeout=25.0):
        time.sleep(0.5); continue           # tag lost / pilot left Offboard: manager holds, wait for the next flip
    while tn('hold_on_tag', hold_s=HOLD_CHUNK_S):
        pass                                # keep holding over tag 0 until CH7 goes back or the tag is lost
