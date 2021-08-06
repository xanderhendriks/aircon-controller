Aircon Controller
=================

Introduction
------------
Flask based air conditioner controller running on raspberry pi.

Locations
^^^^^^^^^
The documentation is stored in github pages: `https://xanderhendriks.github.io/aircon-controller <https://xanderhendriks.github.io/aircon-controller>`_ and the source files are in github: `https://github.com/xanderhendriks/aircon-controller <https://github.com/xanderhendriks/aircon-controller>`_

Installation
------------
The Aircon Controller runs on a standard RaspOS Lite image. Before inserting the SD Card in the RPi create an empty file with the name ssh in the boot drive to enable ssh.

Once started up connect to the device and change the hostname to **tv-slider** by replacing **raspberrypi** in the following files:

- /etc/hosts
- /etc/hostname

Having a static IP can be convenient to find the device on the LAN and this can be done by updating the **/etc/dhcpcd.conf**. The **Example static IP configuration** section in the file shows how.

clone the repo in the **/home/pi** directory and execute the following commands:

1. Install pigpio::

    sudo apt-get install pigpio
    sudo systemctl start pigpiod
    sudo systemctl enable pigpiod

2. Install the required Python packages: ``pip3 install -r scripts/requirements.txt``
3. Create a symbolic link for the service: ``sudo ln -s /home/pi/aircon-controller/linux/etc/systemd/system/aircon-controller.service /etc/systemd/system/aircon-controller.service``

Configuration
-------------
The device listens to the MQTT broker as specified in the AirconControllerMqtt class with the following parameters:

- MQTT_SERVER: set to 192.168.0.253
- MQTT_PORT: set to 1883

Usage
-----
Start the service with the following command:

``sudo systemctl start aircon-controller``

Now the device can be access at the following url: `aircon:5000 <http://aircon:5000>`_
