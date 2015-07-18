#!/usr/bin/env python

import threading
import sys
import json
import zmq
import rospy

from actionlib import SimpleActionServer as ActionServer

from pandora_gui_msgs.msg import ValidateVictimGUIAction
from pandora_gui_msgs.msg import ValidateVictimGUIResult

RESPONSE_PORT = "6667"
SEND_PORT = "6666"


class VictimValidator(object):

    def __init__(self, ros_topic, gui_ip):

        # Action server configuration.
        self.operator_responded = threading.Event()
        self.ros_topic = ros_topic
        self.result = ValidateVictimGUIResult()
        self.victim_found = False
        self.action = ActionServer(self.ros_topic, ValidateVictimGUIAction,
                                   execute_cb=self.handle_goals,
                                   auto_start=False)
        # ZMQ server configuration.
        self.context = zmq.Context()

        print("Listening for victim validation at " + gui_ip + ":" +
              RESPONSE_PORT)
        self.response_receiver = self.context.socket(zmq.SUB)
        self.response_receiver.connect('tcp://' + gui_ip + ':' + RESPONSE_PORT)
        self.response_receiver.setsockopt(zmq.SUBSCRIBE, 'victim_validation')

        self.alert_publisher = self.context.socket(zmq.PUB)

        print("Sending victim alerts at port " + SEND_PORT)
        self.alert_publisher.bind('tcp://*:' + SEND_PORT)

        # Start the action server.
        self.action.start()

    def handle_goals(self, goal):

        self.operator_responded.clear()

        self.current_goal = json.dumps({
            "id": goal.victimId,
            "x": goal.victimFoundx,
            "y": goal.victimFoundy,
            "probability": goal.probability,
            "sensors": goal.sensorIDsFound})

        if self.action.is_preempt_requested():
            print('Preempting validate victim action')
            self.operator_responded.clear()
            self.action.set_preempted()

        # Send the goal to the subscribers.
        print('Received goal from the agent...')
        self.alert_publisher.send('%s %s' % ('victim_goal', self.current_goal))
        print('Waiting for operator response...')
        self.operator_responded.wait()

        # Send the response to the client.
        self.result.victimValid = self.operator_response
        self.action.set_succeeded(self.result)

        # Reset the environment.
        self.operator_responded.clear()

    def start(self):
        while True:
            self.operator_responded.clear()
            print('Waiting for message')
            try:
                res = self.response_receiver.recv()

                if res == 'true':
                    self.operator_response = True
                    self.operator_responded.set()
                    print("Received " + str(self.operator_response))
                elif res == 'false':
                    self.operator_responded.set()
                    self.operator_response = False
                    print("Received " + str(self.operator_response))

            except KeyboardInterrupt:
                print("Interrupt received, proceeding...")


if __name__ == '__main__':

    rospy.init_node('bridge_server')
    if len(sys.argv) > 1:
        gui_ip = sys.argv[1]
    else:
        gui_ip = '192.168.0.120'

    server = VictimValidator('/gui/validate_victim', gui_ip)
    server.start()
