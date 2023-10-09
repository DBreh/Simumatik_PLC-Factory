import time
from Controller import UDP_Controller
import logging
import paho.mqtt.client as mqtt  # Use 'pip install paho-mqtt' to install
import random

if __name__ == '__main__':

    # SETUP: MQTT  ----------------------------------------------------
    # Params
    BROKER_IP_ADDRESS = "127.0.0.1"
    BROKER_PORT = 1883
    # Define input and output topics for MQTT
    topic_prefix = "Factory/"
    Dashboard_variables = {
        f'{topic_prefix}Start_Machine_Right': 'true',
        f'{topic_prefix}Start_Machine_Left': 'true',
        f'{topic_prefix}Lid_Right': 'true',
        f'{topic_prefix}Lid_Left': 'true',
        f'{topic_prefix}Reset_Right': 'false',
        f'{topic_prefix}Reset_Left': 'false',
        f'{topic_prefix}Right_Has_Error': 'false',
        f'{topic_prefix}Left_Has_Error': 'false',
        f'{topic_prefix}Cell_Right_Counter': '0.0',
        f'{topic_prefix}Cell_Left_Counter': '0.0',
        f'{topic_prefix}Cell_Left_Rate': '0.0',
        f'{topic_prefix}Cell_Right_Rate': '0.0',
        f'{topic_prefix}Longterm_Right_Rate': '0.0',
        f'{topic_prefix}Longterm_Left_Rate': '0.0',
        f'{topic_prefix}Longterm_Total_Rate': '0.0',
        f'{topic_prefix}Total_Rate': '0.0',
        f'{topic_prefix}Total_Production': '0.0',
        f'{topic_prefix}Error_Time_Right': '0.0',
        f'{topic_prefix}Idle_Time_Right': '0.0',
        f'{topic_prefix}Busy_Time_Right': '0.0',
        f'{topic_prefix}Error_Time_Left': '0.0',
        f'{topic_prefix}Idle_Time_Left': '0.0',
        f'{topic_prefix}Busy_Time_Left': '0.0',
        f'{topic_prefix}OEE_Left': '0.0',
        f'{topic_prefix}OEE_Right': '0.0',
        f'{topic_prefix}Absolut_Time': '0.0',
        f'{topic_prefix}Product_Finished': 'false',
        f'{topic_prefix}Batch_Size': '0.0',
        f'{topic_prefix}Batch_Production': 'false'
    }


    # Subscription method
    def onMessage(client, userdata, message):
        # Decode value, and update the input dictionary with the new one
        value = str(message.payload.decode('utf-8'))
        if message.topic in Dashboard_variables:
            Dashboard_variables[message.topic] = value
            # print("topic read: ", message.topic, value)
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
    RIGHT_FEED_SEQ = 0
    RIGHT_OUT_SEQ = 0
    LEFT_FEED_SEQ = 0
    LEFT_OUT_SEQ = 0
    start_time = time.perf_counter()
    start_delay_time = start_time
    switch = True
    reached_end = False
    test = True
    production_rate_left = 0
    production_history_left = [time.perf_counter()]
    production_history_right = [time.perf_counter()]
    total_rate = 0
    hourly_rate_right = 0
    hourly_rate_left = 0
    diff_left = []
    diff_right = []
    longterm_rate_right = 0
    longterm_rate_left = 0
    absolut_time = 0

    busy_time_right = 0
    error_time_right = 0
    idle_time_right = 0

    busy_time_left = 0
    error_time_left = 0
    idle_time_left = 0

    last_time_right = time.perf_counter()
    last_time_left = time.perf_counter()

    last_spawn_left = time.perf_counter()

    # Control loop
    while True:
        # Start by getting the updated inputs. List of inputs:
        [_, _, _, _,
         _, _, _, LINE_SENSOR_END,
         CELL_RIGHT_PROGRESS, CELL_RIGHT_BUSY, CELL_RIGHT_ERROR, CELL_RIGHT_DOOR_OPEN,
         RIGHT_SENSOR_OUT2, RIGHT_SENSOR_OUT1, RIGHT_SENSOR_IN, RIGHT_SENSOR_DROP] = _controller.getMappedValue(
            "PLC_INPUTS_1")
        [_, _, _, _,
         _, _, _, _,
         CELL_LEFT_PROGRESS, CELL_LEFT_BUSY, CELL_LEFT_ERROR, CELL_LEFT_DOOR_OPEN,
         LEFT_SENSOR_OUT2, LEFT_SENSOR_OUT1, LEFT_SENSOR_IN, LEFT_SENSOR_DROP] = _controller.getMappedValue(
            "PLC_INPUTS_2")
        clock = time.perf_counter()

        # --------- RIGHT Cell ---------

        CELL_RIGHT_LIDS = Dashboard_variables[f'{topic_prefix}Lid_Right'] == 'true'


        # --------- LEFT Cell ---------

        CELL_LEFT_LIDS = Dashboard_variables[f'{topic_prefix}Lid_Left'] == 'true'

        if CELL_RIGHT_ERROR:
            Dashboard_variables[topic_prefix + 'Right_Has_Error'] = "true"
            modifyVariable(mqtt_client, topic_prefix + 'Right_Has_Error')
        else:
            Dashboard_variables[topic_prefix + 'Right_Has_Error'] = "false"
            modifyVariable(mqtt_client, topic_prefix + 'Right_Has_Error')

        if CELL_LEFT_ERROR:
            Dashboard_variables[topic_prefix + 'Left_Has_Error'] = "true"
            modifyVariable(mqtt_client, topic_prefix + 'Left_Has_Error')
        else:
            Dashboard_variables[topic_prefix + 'Left_Has_Error'] = "false"
            modifyVariable(mqtt_client, topic_prefix + 'Left_Has_Error')




        if CELL_LEFT_ERROR:
            current_time_left = time.perf_counter()
            error_time_left = error_time_left + (current_time_left - last_time_left)
            last_time_left = current_time_left
            Dashboard_variables[topic_prefix + 'Error_Time_Left'] = str(round(error_time_left, 1))
            modifyVariable(mqtt_client, topic_prefix + 'Error_Time_Left')
        elif CELL_LEFT_BUSY:
            current_time_left = time.perf_counter()
            busy_time_left = busy_time_left + (current_time_left - last_time_left)
            last_time_left = current_time_left
            Dashboard_variables[topic_prefix + 'Busy_Time_Left'] = str(round(busy_time_left, 0))
            modifyVariable(mqtt_client, topic_prefix + 'Busy_Time_Left')
        elif CELL_LEFT_STOP is True and CELL_RIGHT_ERROR is False:
            current_time_left = time.perf_counter()
            idle_time_left = idle_time_left + (current_time_left - last_time_left)
            last_time_left = current_time_left
            Dashboard_variables[topic_prefix + 'Idle_Time_Left'] = str(round(idle_time_left, 0))
            modifyVariable(mqtt_client, topic_prefix + 'Idle_Time_Left')




        if CELL_RIGHT_ERROR:
            current_time_right = time.perf_counter()
            error_time_right = error_time_right + (current_time_right - last_time_right)
            last_time_right = current_time_right
            Dashboard_variables[topic_prefix + 'Error_Time_Right'] = str(round(error_time_right, 1))
            modifyVariable(mqtt_client, topic_prefix + 'Error_Time_Right')
        elif CELL_RIGHT_BUSY:
            current_time_right = time.perf_counter()
            busy_time_right = busy_time_right + (current_time_right - last_time_right)
            last_time_right = current_time_right
            Dashboard_variables[topic_prefix + 'Busy_Time_Right'] = str(round(busy_time_right, 0))
            modifyVariable(mqtt_client, topic_prefix + 'Busy_Time_Right')
        elif CELL_RIGHT_STOP is True and CELL_RIGHT_ERROR is False:
            current_time_right = time.perf_counter()
            idle_time_right = idle_time_right + (current_time_right - last_time_right)
            last_time_right = current_time_right
            Dashboard_variables[topic_prefix + 'Idle_Time_Right'] = str(round(idle_time_right, 0))
            modifyVariable(mqtt_client, topic_prefix + 'Idle_Time_Right')


        absolut_time = time.perf_counter() - start_time
        Dashboard_variables[topic_prefix + 'Absolut_Time'] = str(round(absolut_time, 0))
        modifyVariable(mqtt_client, topic_prefix + 'Absolut_Time')

        Dashboard_variables[topic_prefix + 'OEE_Right'] = str(round(busy_time_right/(absolut_time-idle_time_right), 2))
        modifyVariable(mqtt_client, topic_prefix + 'OEE_Right')

        Dashboard_variables[topic_prefix + 'OEE_Left'] = str(round(busy_time_left/(absolut_time-idle_time_left), 2))
        modifyVariable(mqtt_client, topic_prefix + 'OEE_Left')


        if Dashboard_variables[topic_prefix + 'Reset_Left'] == 'true':
            CELL_LEFT_RESET = True
            CELL_LEFT_STOP = False
            CELL_LEFT_START = True
            Dashboard_variables[topic_prefix + 'Reset_Left'] = "false"
            modifyVariable(mqtt_client, topic_prefix + 'Reset_Left')
            Dashboard_variables[topic_prefix + 'Left_Has_Error'] = "false"
            modifyVariable(mqtt_client, topic_prefix + 'Left_Has_Error')
        else:
            CELL_LEFT_RESET = False
            pass

        if Dashboard_variables[topic_prefix + 'Reset_Right'] == 'true':
            CELL_RIGHT_RESET = True
            CELL_RIGHT_STOP = False
            CELL_RIGHT_START = True
            Dashboard_variables[topic_prefix + 'Reset_Right'] = "false"
            modifyVariable(mqtt_client, topic_prefix + 'Reset_Left')
            Dashboard_variables[topic_prefix + 'Right_Has_Error'] = "false"
            modifyVariable(mqtt_client, topic_prefix + 'Right_Has_Error')
        else:
            CELL_RIGHT_RESET = False
            pass

        if Dashboard_variables[topic_prefix + 'Batch_Production'] == 'false' or Dashboard_variables[
            topic_prefix + 'Batch_Production'] == 'true' and float(
                Dashboard_variables[topic_prefix + 'Batch_Size']) > 0:
            CELL_RIGHT_START = Dashboard_variables[f'{topic_prefix}Start_Machine_Right'] == 'true'
            CELL_RIGHT_STOP = Dashboard_variables[f'{topic_prefix}Start_Machine_Right'] == 'false'
            CELL_LEFT_START = Dashboard_variables[f'{topic_prefix}Start_Machine_Left'] == 'true'
            CELL_LEFT_STOP = Dashboard_variables[f'{topic_prefix}Start_Machine_Left'] == 'false'
        else:
            CELL_LEFT_STOP = True
            CELL_LEFT_START = False
            CELL_RIGHT_STOP = True
            CELL_RIGHT_START = False

        # --------- Left sequence ---------
        if time.perf_counter() - start_time > 10:
            # Drop product
            if LEFT_FEED_SEQ == 0 and time.perf_counter() > last_spawn_left+4:
                if LEFT_SENSOR_DROP is False:
                    DROP_PROD_LEFT = True
                LEFT_FEED_SEQ = 1
                print(f"LEFT_FEED_SEQ = {LEFT_FEED_SEQ}")
                last_spawn_left = time.perf_counter()
            # Wait for sensor
            elif LEFT_FEED_SEQ == 1:
                if LEFT_SENSOR_DROP:
                    DROP_PROD_LEFT = False
                    CONV_IN_LEFT = True
                    LEFT_FEED_SEQ = 2
                    print(f"LEFT_FEED_SEQ = {LEFT_FEED_SEQ}")
            # Move forward
            elif LEFT_FEED_SEQ == 2:
                if LEFT_SENSOR_IN:
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
            else:
                print("Fast spawn left line prevented")
                DROP_PROD_LEFT = False

            # Product done
            if LEFT_OUT_SEQ == 0:
                if LEFT_SENSOR_OUT1:
                    CONV_OUT1_LEFT = True
                    CONV_OUT2_LEFT = True
                    Dashboard_variables[topic_prefix + 'Cell_Left_Counter'] = str(
                        float(Dashboard_variables[topic_prefix + 'Cell_Left_Counter']) + 1)
                    modifyVariable(mqtt_client, topic_prefix + 'Cell_Left_Counter')
                    production_history_left.append(time.perf_counter())

                    if len(production_history_left) > 1:
                        diff_left.append(production_history_left[-1] - production_history_left[-2])
                        longterm_rate_left = round(3600/(sum(diff_left)/len(diff_left)), 2)
                        hourly_rate_left = round(3600 / diff_left[-1], 2)
                        Dashboard_variables[topic_prefix + 'Cell_Left_Rate'] = str(hourly_rate_left)
                        modifyVariable(mqtt_client, topic_prefix + 'Cell_Left_Rate')
                        Dashboard_variables[topic_prefix + 'Longterm_Left_Rate'] = str(longterm_rate_left)
                        modifyVariable(mqtt_client, topic_prefix + 'Longterm_Left_Rate')
                        Dashboard_variables[topic_prefix + 'Longterm_Total_Rate'] = str(round(hourly_rate_right+hourly_rate_left, 2))
                        modifyVariable(mqtt_client, topic_prefix + 'Longterm_Total_Rate')

                    if Dashboard_variables[topic_prefix + 'Batch_Production'] == "true":
                        Dashboard_variables[topic_prefix + 'Product_Finished'] = "true"
                        modifyVariable(mqtt_client, topic_prefix + 'Product_Finished')
                    LEFT_OUT_SEQ = 1

            # Product before output Line
            elif LEFT_OUT_SEQ == 1:
                if LEFT_SENSOR_OUT2:
                    CONV_OUT1_LEFT = False
                    LEFT_OUT_SEQ = 0
            # Product to output Line
            elif LEFT_OUT_SEQ == 2:
                if LINE_SENSOR_END:
                    CONV_OUT2_LEFT = False
                    LEFT_OUT_SEQ = 0

        # --------- RIGHT sequence ---------
        if time.perf_counter() - start_time > 10:
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
                    Dashboard_variables[topic_prefix + 'Cell_Right_Counter'] = str(
                        float(Dashboard_variables[topic_prefix + 'Cell_Right_Counter']) + 1)
                    modifyVariable(mqtt_client, topic_prefix + 'Cell_Right_Counter')
                    production_history_right.append(time.perf_counter())

                    if len(production_history_right) > 1:
                        diff_right.append(production_history_right[-1] - production_history_right[-2])
                        longterm_rate_right = round(3600/(sum(diff_right)/len(diff_right)), 2)
                        hourly_rate_right = round(3600 / diff_right[-1], 2)

                        Dashboard_variables[topic_prefix + 'Cell_Right_Rate'] = str(hourly_rate_right)
                        modifyVariable(mqtt_client, topic_prefix + 'Cell_Right_Rate')
                        Dashboard_variables[topic_prefix + 'Longterm_Right_Rate'] = str(longterm_rate_right)
                        modifyVariable(mqtt_client, topic_prefix + 'Longterm_Right_Rate')
                        Dashboard_variables[topic_prefix + 'Longterm_Total_Rate'] = str(round(hourly_rate_right+hourly_rate_left, 2))
                        modifyVariable(mqtt_client, topic_prefix + 'Longterm_Total_Rate')


                    if Dashboard_variables[topic_prefix + 'Batch_Production'] == "true":
                        print("sent decreasor")
                        Dashboard_variables[topic_prefix + 'Product_Finished'] = "true"
                        modifyVariable(mqtt_client, topic_prefix + 'Product_Finished')
                    RIGHT_OUT_SEQ = 1
            # Product before output Line
            elif RIGHT_OUT_SEQ == 1:
                if RIGHT_SENSOR_OUT2:
                    CONV_OUT1_RIGHT = False
                    RIGHT_OUT_SEQ = 0
            # Product to output Line
            elif RIGHT_OUT_SEQ == 2:
                if LINE_SENSOR_END:
                    CONV_OUT2_RIGHT = False
                    RIGHT_OUT_SEQ = 0

        # Collison avoidance

        if (LEFT_SENSOR_OUT2 and RIGHT_SENSOR_OUT2) or reached_end is True:
            CONV_OUT2_RIGHT = False
            CONV_OUT2_LEFT = True
            reached_end = True
            if switch is True:
                start_delay_time = time.perf_counter()
                switch = False
            if time.perf_counter() - start_delay_time > 4:
                reached_end = False
                switch = True
                CONV_OUT2_RIGHT = True
                CONV_OUT2_LEFT = True

        if CELL_LEFT_STOP:
            total_rate = round(hourly_rate_right, 2)
            Dashboard_variables[topic_prefix + 'Cell_Left_Rate'] = "0 //Machine is currently stopped"
            modifyVariable(mqtt_client, topic_prefix + 'Cell_Left_Rate')
        elif CELL_RIGHT_STOP:
            total_rate = round(hourly_rate_left, 2)
            Dashboard_variables[topic_prefix + 'Cell_Right_Rate'] = "0 //Machine is currently stopped"
            modifyVariable(mqtt_client, topic_prefix + 'Cell_Right_Rate')
        elif CELL_RIGHT_STOP and CELL_LEFT_STOP:
            total_rate = 0
        else:
            total_rate = round(hourly_rate_right + hourly_rate_left, 2)

        Dashboard_variables[topic_prefix + 'Total_Rate'] = str(total_rate)
        modifyVariable(mqtt_client, topic_prefix + 'Total_Rate')

        Dashboard_variables[topic_prefix + 'Total_Production'] = str(float(Dashboard_variables[topic_prefix + 'Cell_Right_Counter'])+float(Dashboard_variables[topic_prefix + 'Cell_Left_Counter']))
        modifyVariable(mqtt_client, topic_prefix + 'Total_Production')



        # --------- Line End ---------
        CONV_OUT_LINE = True
        # print(CELL_RIGHT_ERROR)

        # Send updated outputs to controller
        _controller.setMappedValue("PLC_OUTPUTS_1",
                                   [False, False, False, False,
                                    False, False, False, CONV_OUT_LINE,
                                    DROP_PROD_RIGHT, CELL_RIGHT_STOP, CELL_RIGHT_START, CELL_RIGHT_RESET,
                                    CELL_RIGHT_LIDS, CONV_OUT2_RIGHT, CONV_OUT1_RIGHT,
                                    CONV_IN_RIGHT])  # cell right lids --> if false produces bases otherwise produces lids
        _controller.setMappedValue("PLC_OUTPUTS_2",
                                   [False, False, False, False,
                                    False, False, False, False,
                                    DROP_PROD_LEFT, CELL_LEFT_STOP, CELL_LEFT_START, CELL_LEFT_RESET,
                                    CELL_LEFT_LIDS, CONV_OUT2_LEFT, CONV_OUT1_LEFT, CONV_IN_LEFT])
        # Sleep for short duration to prevent taking much CPU power
        time.sleep(0.05)
