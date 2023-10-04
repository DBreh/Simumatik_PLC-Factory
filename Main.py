import time
from Controller import UDP_Controller
import logging
import paho.mqtt.client as mqtt # Use 'pip install paho-mqtt' to install

if __name__ == '__main__':
    
    # SETUP: MQTT  ----------------------------------------------------
    # Params
    BROKER_IP_ADDRESS = "127.0.0.1"
    BROKER_PORT = 1883
    # Define input and output topics for MQTT
    topic_prefix = "Factory/"
    Dashboard_variables = {
        f'{topic_prefix}Start_Machine': 'true',
        f'{topic_prefix}Cell_Right_Counter': '0.0',
        }
    # Subscription method
    def onMessage(client, userdata, message):
        # Decode value, and update the input dictionary with the new one
        value = str(message.payload.decode('utf-8'))
        if message.topic in Dashboard_variables:
            Dashboard_variables[message.topic] = value
            #print("topic read: ", message.topic, value)
        else:
            print("topic not found: ", message.topic, value)
    # Publishing method
    def modifyVariable(client, topic):
        if client and topic in Dashboard_variables:
            client.publish(topic, Dashboard_variables[topic])
    # Connect to Broker
    try:
        mqtt_client = None
        # Create the MQTT client
        mqtt_client = mqtt.Client('Dashboard')
        mqtt_client.on_message = onMessage
        mqtt_client.connect(BROKER_IP_ADDRESS, port=BROKER_PORT, keepalive=60)
        mqtt_client.loop_start()
        # Subscribe to all variables
        mqtt_client.subscribe([(topic, 2) for topic in Dashboard_variables])
        # Publish initial values
        for topic in Dashboard_variables:
            modifyVariable(mqtt_client, topic)
        print(f"Connect to MQTT Broker at {BROKER_IP_ADDRESS}:{BROKER_PORT}.")
    except:
        print("Cannot connect to MQTT Broker.")

    # SETUP: Simumatik UDP connection ------------------------------------
    _controller = UDP_Controller(log_lever=logging.ERROR)
    _controller.addVariable("PLC_INPUTS_1", "word", 0)
    _controller.addVariable("PLC_INPUTS_2", "word", 0)
    _controller.addVariable("PLC_OUTPUTS_1", "word", 0)
    _controller.addVariable("PLC_OUTPUTS_2", "word", 0)
    _controller.start()
    # Initialize all outputs
    CONV_IN_RIGHT = CONV_OUT1_RIGHT = CONV_OUT2_RIGHT = CELL_RIGHT_LIDS = CELL_RIGHT_RESET = CELL_RIGHT_START = CELL_RIGHT_STOP = DROP_PROD_RIGHT = False
    CONV_OUT_LINE = False
    CONV_IN_LEFT = CONV_OUT1_LEFT = CONV_OUT2_LEFT = CELL_LEFT_LIDS = CELL_LEFT_RESET = CELL_LEFT_START = CELL_LEFT_STOP = DROP_PROD_LEFT = False

    # CONTROL LOGIC: ----------------------------------------------------
    # Initialize variables
    LEFT_FEED_SEQ = 0
    LEFT_OUT_SEQ = 0
    RIGHT_FEED_SEQ = 0
    RIGHT_OUT_SEQ = 0
    start_time = time.perf_counter()
    
    # Control loop
    while True:
        # Start by getting the updated inputs. List of inputs:
        [_, _, _, _, 
         _, _, _, LINE_SENSOR_END, 
         CELL_RIGHT_PROGRESS, CELL_RIGHT_BUSY, CELL_RIGHT_ERROR, CELL_RIGHT_DOOR_OPEN, 
         RIGHT_SENSOR_OUT2, RIGHT_SENSOR_OUT1, RIGHT_SENSOR_IN, RIGHT_SENSOR_DROP] = _controller.getMappedValue("PLC_INPUTS_1")
        [_, _, _, _,
         _, _, _, _, 
         CELL_LEFT_PROGRESS, CELL_LEFT_BUSY, CELL_LEFT_ERROR, CELL_LEFT_DOOR_OPEN, 
         LEFT_SENSOR_OUT2, LEFT_SENSOR_OUT1, LEFT_SENSOR_IN, LEFT_SENSOR_DROP] = _controller.getMappedValue("PLC_INPUTS_2")
        clock = time.perf_counter()

        # --------- RIGHT Cell ---------
        CELL_RIGHT_START = Dashboard_variables[f'{topic_prefix}Start_Machine'] == 'true'
        CELL_RIGHT_STOP = Dashboard_variables[f'{topic_prefix}Start_Machine'] == 'false'

        # --------- LEFT Cell ---------
        CELL_LEFT_START = Dashboard_variables[f'{topic_prefix}Start_Machine'] == 'true'
        CELL_LEFT_STOP = Dashboard_variables[f'{topic_prefix}Start_Machine'] == 'false'
        
        # --------- RIGHT sequence ---------
        if time.perf_counter() - start_time> 10:
            # Drop product 
            if RIGHT_FEED_SEQ == 0:
                DROP_PROD_RIGHT = True
                RIGHT_FEED_SEQ = 1
                print(f"RIGHT_FEED_SEQ = {RIGHT_FEED_SEQ}")
            # Wait for sensor
            elif RIGHT_FEED_SEQ == 1:
                if RIGHT_SENSOR_DROP:
                    DROP_PROD_RIGHT = False
                    CONV_IN_RIGHT = True
                    RIGHT_FEED_SEQ = 2
                    print(f"RIGHT_FEED_SEQ = {RIGHT_FEED_SEQ}")
            # Move forward
            elif RIGHT_FEED_SEQ == 2:
                if RIGHT_SENSOR_IN:
                    CONV_IN_RIGHT = False
                    RIGHT_FEED_SEQ = 3
                    print(f"RIGHT_FEED_SEQ = {RIGHT_FEED_SEQ}")
            # Feed machine
            elif RIGHT_FEED_SEQ == 3:
                if not CELL_RIGHT_ERROR and not CELL_RIGHT_BUSY:
                    CONV_IN_RIGHT = True
                    RIGHT_FEED_SEQ = 4
                    print(f"RIGHT_FEED_SEQ = {RIGHT_FEED_SEQ}")
            # Feed machine
            elif RIGHT_FEED_SEQ == 4:
                if not RIGHT_SENSOR_IN:
                    CONV_IN_RIGHT = False
                    RIGHT_FEED_SEQ = 0
                    print(f"RIGHT_FEED_SEQ = {RIGHT_FEED_SEQ}")

            # Product done
            if RIGHT_OUT_SEQ == 0:
                if RIGHT_SENSOR_OUT1:
                    CONV_OUT1_RIGHT = True
                    CONV_OUT2_RIGHT = True
                    Dashboard_variables[topic_prefix+'Cell_Right_Counter'] = str(float(Dashboard_variables[topic_prefix+'Cell_Right_Counter'])+1)
                    modifyVariable(mqtt_client, topic_prefix+'Cell_Right_Counter') 
                    RIGHT_OUT_SEQ = 1
            # Product before output Line
            elif RIGHT_OUT_SEQ == 1:
                if RIGHT_SENSOR_OUT2:
                    CONV_OUT1_RIGHT = False
                    RIGHT_OUT_SEQ = 2
            # Product to output Line
            elif RIGHT_OUT_SEQ == 2:
                if LINE_SENSOR_END:
                    CONV_OUT2_RIGHT = False
                    RIGHT_OUT_SEQ = 0


        # --------- Left sequence ---------
        if time.perf_counter() - start_time > 10:
            # Drop product
            if LEFT_FEED_SEQ == 0:
                DROP_PROD_LEFT = True
                LEFT_FEED_SEQ = 1
                print(f"LEFT_FEED_SEQ = {LEFT_FEED_SEQ}")
            # Wait for sensor
            elif LEFT_FEED_SEQ == 1:
                if LEFT_SENSOR_DROP:
                    DROP_PROD_LEFT = False
                    CONV_IN_LEFT = True
                    LEFT_FEED_SEQ = 2
                    print(f"LEFT_FEED_SEQ = {LEFT_FEED_SEQ}")
            # Move forward
            elif LEFT_FEED_SEQ == 2:
                if RIGHT_SENSOR_IN:
                    CONV_IN_LEFT = False
                    LEFT_FEED_SEQ = 3
                    print(f"LEFT_FEED_SEQ = {LEFT_FEED_SEQ}")
            # Feed machine
            elif LEFT_FEED_SEQ == 3:
                if not CELL_LEFT_ERROR and not CELL_LEFT_BUSY:
                    CONV_IN_LEFT = True
                    LEFT_FEED_SEQ = 4
                    print(f"LEFT_FEED_SEQ = {LEFT_FEED_SEQ}")
            # Feed machine
            elif LEFT_FEED_SEQ == 4:
                if not LEFT_SENSOR_IN:
                    CONV_IN_LEFT = False
                    LEFT_FEED_SEQ = 0
                    print(f"LEFT_FEED_SEQ = {LEFT_FEED_SEQ}")

            # Product done
            if LEFT_OUT_SEQ == 0:
                if LEFT_SENSOR_OUT1:
                    CONV_OUT1_LEFT = True
                    CONV_OUT2_LEFT = True
                    #Dashboard_variables[topic_prefix + 'Cell_Left_Counter'] = str(float(Dashboard_variables[topic_prefix + 'Cell_Left_Counter']) + 1)
                    modifyVariable(mqtt_client, topic_prefix + 'Cell_Left_Counter')
                    LEFT_OUT_SEQ = 1

            # Product before output Line
            elif LEFT_OUT_SEQ == 1:
                if LEFT_SENSOR_OUT2:
                    CONV_OUT1_LEFT = False
                    LEFT_OUT_SEQ = 2
            # Product to output Line
            elif LEFT_OUT_SEQ == 2:
                if LINE_SENSOR_END:
                    CONV_OUT2_LEFT = False
                    LEFT_OUT_SEQ = 0



        # --------- Line End ---------
        CONV_OUT_LINE = True
        
        # Send updated outputs to controller
        _controller.setMappedValue("PLC_OUTPUTS_1", 
                                   [False, False, False, False, 
                                    False, False, False, CONV_OUT_LINE, 
                                    DROP_PROD_RIGHT, CELL_RIGHT_STOP, CELL_RIGHT_START, CELL_RIGHT_RESET,
                                    CELL_RIGHT_LIDS, CONV_OUT2_RIGHT, CONV_OUT1_RIGHT, CONV_IN_RIGHT])
        _controller.setMappedValue("PLC_OUTPUTS_2", 
                                   [False, False, False, False, 
                                    False, False, False, False,
                                    DROP_PROD_LEFT, CELL_LEFT_STOP, CELL_LEFT_START, CELL_LEFT_RESET, 
                                    CELL_LEFT_LIDS, CONV_OUT2_LEFT, CONV_OUT1_LEFT, CONV_IN_LEFT])
        # Sleep for short duration to prevent taking much CPU power
        time.sleep(0.01)
