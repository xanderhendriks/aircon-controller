#!/usr/bin/env python

import json
import logging
import pigpio
import time
import threading
from flask import Flask, render_template
import paho.mqtt.subscribe as subscribe
import paho.mqtt.client as mqttClient

logger = logging.getLogger('aircon_flask_server')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
file_handle = logging.FileHandler('/home/pi/aircon-controller/aircon_comms.log')
file_handle.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handle.setFormatter(formatter)

# add the handlers to the logger
logger.addHandler(file_handle)


app = Flask(__name__)
pi = pigpio.pi()
mqtt_client = mqttClient.Client("Python")
mqtt_client.connect('192.168.0.253', 1883)

INTER_WORD_TIME = 7000
ONE_TIME = 400
ZERO_TIME = 1350

DELTA_TEMPERATURE = 0.75

SENSORS = ['outdoor_temperature', 'livingroom_temperature', 'homeoffice_temperature', 'masterbedroom_temperature']

timing = 0
last_tick = 0
data = 0
last_data = 0
bit_index = 0

sensor_payloads = {}
control_active = False
temperature_set = 20


@app.route("/")
def index():
    update_sensor_status()
    return render_template("index.html", temperatures=sensor_payloads)


@app.route("/control/toggle")
def control_toggle():
    global control_active

    toggle_on_off()
    return 'OK'


@app.route("/control/status")
def control_status():
    global last_data
    status = {}
    temperatures = {}

    status['raw'] = bin(last_data)
    status['aircon_active'] = last_data & (0x01 << 31) == (0x01 << 31)
    if last_data & (0x01 << 24) == (0x01 << 24):
        status['aircon_mode'] = 'heating'
    elif last_data & (0x01 << 39) == (0x01 << 39):
        status['aircon_mode'] = 'cooling'
    else:
        status['aircon_mode'] = 'off'
    status['control_active'] = control_active
    status['zone1'] = is_zone_active(1)
    status['zone2'] = is_zone_active(2)
    status['zone3'] = is_zone_active(3)
    temperatures['set'] = temperature_set
    update_sensor_status()
    for sensor in SENSORS:
        temperatures[sensor] = sensor_payloads[sensor]['temperature']

    status['temperatures'] = temperatures

    return json.dumps(status)


@app.route("/control/temperature/set/<value>")
def control_temperature_set(value):
    global temperature_set

    temperature_set = int(value)
    return '%d' % temperature_set


@app.route("/control/temperature/get")
def control_temperature_get():
    return '%d' % temperature_set


@app.route("/log")
def log():
    file = open('/home/pi/aircon-controller/aircon-controller.log')
    logs = file.read()

    return logs


@app.route("/sense/<location>/<sensor>")
def sense_sensor(location, sensor):
    update_sensor_status()
    return json.dumps(sensor_payloads['%s_%s' % (location, sensor)])


def is_zone_active(zone):
    zones = {1: 18, 2: 25, 3: 27}

    return last_data & (0x01 << zones[zone]) == (0x01 << zones[zone])


def active_sensor_temperature():
    zones = {1: 'masterbedroom_temperature', 2: 'homeoffice_temperature', 3: 'livingroom_temperature'}

    for zone in zones:
        if is_zone_active(zone):
            return sensor_payloads[zones[zone]]['temperature']


def get_area_string(data):
    if data == 1:
        area_string = 'Master'
    elif data == 2:
        area_string = 'Bedrooms'
    elif data == 3:
        area_string = 'Living + Bedrooms'
    else:
        area_string = 'Area data invalid %d' % data

    return area_string


def get_fan_string(data):
    fan_data = (data & 0x07 << 28) >> 28

    if fan_data == 0:
        fan_string = 'Off'
    elif fan_data == 1:
        fan_string = 'Low'
    elif fan_data == 2:
        fan_string = 'Medium'
    elif fan_data == 4:
        fan_string = 'High'
    else:
        fan_string = 'Fan data invalid %d' % data

    return fan_string


def received_data(data):
    return 'Raw data: 0x%010X, Area: %s, Fan: %s, Control data: 0x%04X\n' % (data,
                                                                             get_area_string(data & 0x0003),
                                                                             get_fan_string((data & 0x0E00) >> 9),
                                                                             (data & ~(0x0E00 | 0x0003)))


def cbf(gpio, level, tick):
    global bit_index
    global last_tick
    global data
    global last_data

    if last_tick != 0:
        timing = tick - last_tick

        if timing > INTER_WORD_TIME:
            bit_index = 0
            data = 0
        elif level == 0:
            pass
        elif timing > ONE_TIME and timing < ZERO_TIME:
            data = (data << 1) + 1
            bit_index += 1
        elif timing > ZERO_TIME:
            data = (data << 1)
            bit_index += 1

        if bit_index == 41:
            if last_data != data:
                logger.info(received_data(data))
                print(data)
                last_data = data

        elif bit_index > 41:
            print('bit_index', bit_index, timing)

    last_tick = tick


def toggle_on_off():
    pi.write(15, 1)
    time.sleep(0.5)
    pi.write(15, 0)


def update_sensor_status():
    global sensor_payloads

    for sensor in SENSORS:
        message = subscribe.simple('zigbee2mqtt/%s' % sensor.replace('_', '/'), hostname='192.168.0.253')
        sensor_payloads[sensor] = json.loads(message.payload)


def update_control():
    aircon_active = last_data & (0x01 << 31) == (0x01 << 31)
    aircon_heating = False  # last_data & (0x01 << 24) == (0x01 << 24)
    mqtt_client.publish('zigbee2mqtt/aircon/current_temperature/get', active_sensor_temperature(), 0, True)

    if control_active:
        if aircon_heating:
            if aircon_active:
                if int(active_sensor_temperature()) > (temperature_set + DELTA_TEMPERATURE):
                    toggle_on_off()
            else:
                if int(active_sensor_temperature()) < (temperature_set - DELTA_TEMPERATURE):
                    toggle_on_off()
        else:
            if aircon_active:
                if int(active_sensor_temperature()) < (temperature_set - DELTA_TEMPERATURE):
                    toggle_on_off()
            else:
                if int(active_sensor_temperature()) > (temperature_set + DELTA_TEMPERATURE):
                    toggle_on_off()

    else:
        if aircon_active:
            toggle_on_off()


def timer_30sec_callback():
    update_sensor_status()
    update_control()

    threading.Timer(30, timer_30sec_callback).start()


def main():
    # Setup aircon controller protocol parser
    pi.set_pull_up_down(14, pigpio.PUD_UP)
    pi.callback(14, pigpio.EITHER_EDGE, cbf)

    # Start 30 sec timer
    timer_30sec_callback()

    # Setup flask server
    app.run(host='0.0.0.0')


if __name__ == "__main__":
    main()
