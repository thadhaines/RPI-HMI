# -*- coding: utf-8 -*-

"""
    RPI HMI v1.0
    Copyright (C) 2017  Thad Haines

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

"""
def Code_Function:
    GUI to test stepping though modes of control to simulate a simple batch
    operation.  Utilizes logging, multithreading, and queueing.

    Queues are used to send status or stop signals across threads, while
    the threads themselves carry out timed operations alloying the main loop to
    continously run and enable the GUI to remain responsive.

    Indivicual mode times will be read in via the associated combo box.
    A function will be called to set pins (and thus the attached relays)
    to desired mode sequence and then sleep the correct amount of time.
"""

'''
def Code_History:
    07/28/16    Initial working version - logs work correctly, cycles work correctly
                GUI update does not work - requires more thought due to scope of 
                variables - i.e. self.Some_Label can only be changed from within
                pyQt main window loop(thread), there fore, some signal is required
                to update label values...  If queue supports floats then the log
                thread can put values into their respective queue, another update_gui
                thread can be running and be triggered to update GUI?...  Update every
                .5 seconds...  Mostly unsure.
                
                Slight code cleanup - decision to split start stop buttons for log
                and process - will allow for safer logging - downside of .5 sec GUI 
                status refresh.  Reconfigure pins function created - this allows the
                GPIO cleanup to be run with the stop button, and then pins easily
                re-assigned with start button...  Don't over think it.
                
    07/29/16    Previous attempts at custom signals failed - removed from code - 
                though problem may have been in the updateGUI function not having
                self as an argument...  
                
    08/04/16    GUI update from thread test succesful - applying to code!  Works!
                Removal of custom signal creation / triggering, general code cleanup
                GUI updates correctly - GUI version considered successfully DONE!
                
    08/15/16    File name now mainwindow_altside.py for use with pyside_GUI_5.py
                Converted from PyQt to PySide for future license ease.
                Added a Log_Status label that should be used to show log status.
                Form (the GUI layout) slightly altered and recompiled.
                *** help(function_name) will print console help ***
                The setEnabled(ToF state) function used to disable/enable alteration
                of mode times while running.
                CamelCase used in function names (no longer print_log() etc....).
                as_of_time Property of GUI altered to be informative.
                
    08/16/16    Minor code cleanup, attempt at making progress bars for modes.
                Progess bar didn't work - current time did.
                Maybe create main GUI signal that updates progress bars everytime
                the main system time changes...  Would have to change type to QlineEdit
                in order to have a changed signal be sent.  Just make it disabled by default
                and remove box?
                
    08/17/16    Alteration of GUI again, addition of WORKING progress bars via an
                update of a 0x0 px lineEdit box called system_time
                
    08/19/16    Minor code cleanup for printing.  LC:  445
    
    08/30/16    Re-arrangement of code, specifically:  Sorting of functions into
                four groups (CTRL, DATA, GUI, LOG) for clearer code stuctrue.
                Addition of collapsable code_info blocks.  LC:  455
                
    11/19/16    9_LED_prototype_01 :  New GUI, different GPIO method - start of
                code re-write to meet final requirements and functionality. 
                Update/ Re-evaluation of all functions. LC: 606
                
    11/21/16    Minor code cleanup for printing.  LC:  620
    
    12/17/16    Addition of exact_wait function - doesn't work as desired...
                Fix of Zero cycle bug 
                Attempt at fixing logging, problem is now that all logs are 
                stored to each previous log as well...  More required...
                Fix of logging issue - added debug flags, fixed unkown display
                bug of current time freezing while prog bar contsinued.
                Had to do with aligmnet of GUI and format of string LC 699 LH 78
                
    12/18/16    Added ADC thermistor code with success , only 1 log error of
                taking too long, usually not a problem.
                LC 752 LH 81
                
    12/28/16    _006 Attempt to correct spotty GUI update behavior via global 
                variables...  Seems to work.  Only used globals for system
                status, not current times, but GUI is updating correctly for 
                the longer (11 minute) tests.
                LC 816 LH 86
                
    01/03/17    _007 Addition of Serial Communication code for pH data.
                LC 836  LH 88
                
	02/23/17	Alteration of cycleThread and disoverMode to account for 'new'
				initialize operation.
                
    03/10/17    009.  Alteration of log time to 1 second to account for slower 
                (.6) avg pH meter update.  
                Setting of debug flags to run pH meter AND temps.
                
    03/20/17    011.    Combining of previous separate updates into one file.
                Since 011 will be default, all debug flags ON, seperate files
                will then link to specific debugs.  Added functionality of 
                having the lookup table and logs in separate directories via 
                the os getcwd feature.  Code now only works from shortcuts...
                
	03/20/17 	012.	Debug for pH only, else same as 011.
    
    03/20/17    013.    Working alpha version. LC 881 LH 130
                
''' 

"""
Module implementing MainWindow.
"""

from PySide.QtCore import Slot
from PySide.QtGui import QMainWindow
from PySide.QtGui import QApplication

from .Ui_mainwindow_004 import Ui_MainWindow    # place to update GUI form

''' Required Imports '''
import Adafruit_ADS1x15 # for reading analog values
import csv              # For Logfile creation
import logging          # For actual logging processes
import os               # For using paths
import random           # For creation of 'dummy' data
import serial           # For Serial object required in pH collection
import smbus            # For GPIO Expander Communication
import sys              # For Serial Communication data size check
import time             # For delays and system time in logs / on display
import threading        # For multithread processing
import queue            # For global acces to boolean flags

''' Global Variables '''
# Debug flags
ADC_DEBUG = 0     # 1 for random temps, else 0 for ADC collection
PH_DEBUG = 1      # 1 for random pH, else 0 for serial communication

# Log and Update Variables
log_interval = 1                    # Time between log entries
log_append = "RPI_HMI_pH_DEBUG_LOG" # Name used to make logs more descriptive
update_GUI_interval = .05           # Time between GUI updates / run counts.

# Queues for multithread flag communication
log_q = queue.Queue(maxsize=0)      # used to stop thread
run_q = queue.Queue(maxsize=0)      # used to show if running or not
first_run = queue.Queue(maxsize=0)  # to denote first run or not
first_run.put(1)                    # first run set as default

# Lnitialize log object Properties
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

#Creation of serial object that matches orion star com specs
if not PH_DEBUG:    # will only create object if required
    OS214 = serial.Serial(
            port='/dev/ttyUSB0',    # may have to change...
            baudrate = 9600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1
           )

'''  ADC Variables '''
# Setup of ADC
# Create an ADS1015 ADC (12-bit) instance on default channel 0x48
adc = Adafruit_ADS1x15.ADS1015()   # Used in get_V
Rs_1 = 9900
Rs_2 = 9900 
num_to_avg = 10    # related to number of sampls to take and average together
data_rate = 128     # actual sps of ADC

'''  Handling of Data Table Import '''
# Opening of file and reading
cwd = os.getcwd()
# use to have lookup table in separate directory
lookup_table = open(cwd+"/code/3950_NTC_lookuptable.csv", newline='')
table_data = csv.reader(lookup_table)

# Creating blank lists for values
temperature_list = []
resistance_list = []

# Populate lists with data
for row in table_data:
    resistance_list.append(float( row[1] )*1000)   # convert to ohms
    temperature_list.append(int(row[0]))

''' Associated Globals of MCP GPIO expanders and initial Configuration '''
# Physical device addresses
Valve_bus       = 0x20      # Specific Device On I2C bus - mcp23008
Pump_Mag_bus    = 0x21      # Specific Device On I2C bus - mcp23008
In_bus          = 0x24      # Specific Device On I2C bus - mcp23017

# Hex relating device to bit for easier coding
FP101 = 0x01
FP102 = 0x02
FP103 = 0x04

EM201 = 0x10
EM202 = 0x20

FV201 = 0x01
FV202 = 0x02
FV203 = 0x04
FV204 = 0x08

# Pin registers on Out bus (O as in out)
pinDir_O = 0x00   # register for pin direction on 23008 (IODIRX)
pinOut_O = 0x09   # register for pin outputs on 23008 (OLATX)

# Pin registers on In Bus (A and B required for 16 channels)
pinDir_A = 0x00   # register for pin direction on A bus (IODIRX)
pinDir_B = 0x01   # register for pin direction on B bus

pinIn_A  = 0x12   # register for pin inputs on A bus (GPIOX)
pinIn_B  = 0x13   # register for pin inputs on B bus

# creation of bus object - used to communicate over i2c bus
I2C = smbus.SMBus(1) 

#set all pins on output mcps as outputs and low -> Forces Standby Initialy
I2C.write_byte_data(Valve_bus, pinDir_O,  0x00)
I2C.write_byte_data(Pump_Mag_bus, pinDir_O,  0x00)

#set all pins on input mcps as inputs
I2C.write_byte_data(In_bus, pinDir_A, 0xFF)
I2C.write_byte_data(In_bus, pinDir_B, 0xFF)

''' Globals for GUI Update '''
var1 = var2 = var3 = 0          # Pump Status
var4 = var5 = var6 = var7 = 0   # Valve Status
var8 = var9 = 0                 # EM status
var10 = var11 = var12 = 0.0     # data points

''' Thread Class Creations '''
class logThread (threading.Thread):
    # Updated 11/19/16
    """
    Thread class that initializes log file, continuosly gets current system 
    status, temperatures, and pH value, then populates log file,  and
    updates the GUI while global que
    """
    def __init__(self, parent, threadID, name):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.parent = parent
        
    def run(self):                       # Action taken by thread upon start
        print("*Running %s" % self.name) 
        initializeLog()
        print("*File initialized, Headers created, Logging Started")
        self.parent.Log_Status.setText("Log Running")  
        printLog(self.parent, self.name, 1)  # 'Endless' Loop - exits via flag
        print("*Stopping " + self.name)
        self.parent.Log_Status.setText("Log Standby")
        QApplication.processEvents()    # forces update of GUI
    
class cycleThread (threading.Thread):
    # init updated 12/28/16
    """
    Thread class forces mode logic to output bus via runmode function and
    'counts' time spent in each mode in order to updates gui.
    """
    def __init__(self, parent, threadID, name):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        
        # Gets total Cycle time from GUI
        # funny conversion of str -> float -> int
        self.Init_Time = int(float(parent.Init_tot.text()))
        self.Side1_Time = int(float(parent.Side_1_tot.text()))
        self.Side2_Time = int(float(parent.Side_2_tot.text()))
        
        # +1 at the end due to combo box behavior, index starts at 0
        # but display values start at 1.
        self.Cycles = int(parent.cb_repeat_cycle.currentIndex()+1)
        self.parent = parent
        
        
    def run(self):     
        # Runs desired modes in order while checking queus.
        print("*Running %s" % self.name) 
        
        # runMode Arguements:  Valve_bus , PM_bus, mode time, CT display, parent
        
        # Initialize Mode
        if self.Init_Time:
            runMode(0x05, 0x01,  self.Init_Time, self.parent.current_Init_Time, self.parent)
        
        cycle_counter = 0
        while cycle_counter < self.Cycles:  # Start of Cyle
            # Side 1 Run
            if self.Side1_Time:
                runMode(0x05, 0x17, self.Side1_Time, self.parent.current_Side_1_Time, self.parent)
            # Side 2 Run
            if self.Side2_Time:
                runMode(0x0A, 0x27, self.Side2_Time, self.parent.current_Side_2_Time, self.parent)
                
            cycle_counter+= 1

        systemOff()
        print("*Stopping " + self.name+".  Entering update only mode...")
 
        while not run_q.empty(): ## run_1 == 1
            #NOTE:Change of system_time signal related to Progress bar / GUI update
            self.parent.system_time.setText('Update GUI!')
            self.parent.system_time.setText(" ")
            time.sleep(update_GUI_interval)

''' CTRL functions '''
def runMode(V_busout, PM_busout, mode_Time, CT_display, parent):
    # Updated 12/18/16
    """
    Set system state. Enters while loop to wait through mode_time.  
    Function breaks out if run_q is empty.  The queue is checked at 
    update_GUI_interval.  Function also updates total run time and
    triggers system_time_changed slot that is used to update GUI progress bars.
    """
    
    if not run_q.empty():   ## run_q == 1

        # Focing state to output busses
        I2C.write_byte_data(Valve_bus, pinOut_O, V_busout )
        I2C.write_byte_data(Pump_Mag_bus, pinOut_O, PM_busout) 
        
        time_start = time.time()    # for start time
        waited = 0
        
        # Entering wait loop
        while waited < (mode_Time- update_GUI_interval*.5):
            if run_q.empty(): ## run_q == 0
                break
            else:
                tot_time = time.time()-time_start
                #print('update time: ', tot_time)   # for debug
                if tot_time < update_GUI_interval:
                    time.sleep(update_GUI_interval-tot_time)
                    waited += update_GUI_interval
                    
                else:
                    print('GUI update taking longer than update interval')
                    waited += tot_time
                
                time_start = time.time()        # for subsequent repeates
                
                wait_String = '{:6.2f}'.format(waited)
                
                CT_display.setText(wait_String)

                # update of total progress counter
                try:
                    current_tot = float(parent.current_Rep_Cycle.text())
                    current_tot += update_GUI_interval
                except ValueError:
                    current_tot = update_GUI_interval;
                    
                parent.current_Rep_Cycle.setText( '{:6.2f}'.format(current_tot))
                
        #NOTE:Change of system_time signal related to Progress bar & GUI update
                parent.system_time.setText('Update Progress Bars & GUI!')
                parent.system_time.setText(" ")  

    else:   #if run_q empty, system goes to standby mode - all off
        systemOff()
    
def systemOff():
    # Updated 11/19/16
    """ Sets system to safe off/standby mode. """
    I2C.write_byte_data(Valve_bus, pinOut_O, 0x00 )
    I2C.write_byte_data(Pump_Mag_bus, pinOut_O, 0x00) 
    
''' DATA functions '''
# As of 12/18/16 : debug flags added. needs real pH functions
def calc_temp(Vcc, Vadc, Rs):
    '''
    Calculates temerature of thermistor based off the VCC and Vadc given known 
    Shunt Value.  Physically built as:
                VCC----Rs--\/---Thermistor----GND
                            L___Vadc_In
    Uses global temperature and resistance lists in order to 
    perform linear approximation.
    '''
    # Find thermistor resistance based off known values
    R_t = (Vadc*Rs) / (Vcc-Vadc) 

    # With known R_t value, find upper and lower limits for linear approx
    upper_ndx = 0
    while R_t < resistance_list[upper_ndx]:
        upper_ndx += 1
        
    lower_ndx = upper_ndx-1

    # linear approximation variables for cleaner equation
    CH = temperature_list[upper_ndx]
    CL = temperature_list[lower_ndx]
    RH = resistance_list[upper_ndx]
    RL = resistance_list[lower_ndx]
    RM = R_t
    # linear approximation calculation
    CM = ( (CH-CL)*(RM-RH) )/(RH-RL) +CH
    
    return CM
    
def get_V(A_IN, GAIN, RATE, FS_V, num_to_avg):
    '''
    Function to get a voltage average from the ADS1015, uses global 
    ADC variables.
    '''
    Vadc = 0;   V_DN = 0;   ndx=0
    
    while ndx < num_to_avg:
        V_DN =  adc.read_adc(A_IN, gain=GAIN, data_rate=RATE)
        Vadc = Vadc + ((V_DN/2047) * FS_V)
        ndx += 1
    
    return Vadc/ndx

def getpH():
    # Used to generate random pH for logging purpose 
    pH = random.random()*2+7
    return pH
    
def getTemp(): 
    # Used to generate random temps for logging purpose 
    temp = random.random()*5+65
    return temp

''' GUI functions '''
# Updated 11/19/16
def convert_time(min, sec):
    # Updated 11/19/16
    """ Takes int values min/sec and returns string of total time """ 
    total_time = min*60
    total_time = total_time + sec
        
    return str(total_time)+'.0'  # string because being passed to GUI

def disoverMode(system_sum):
    # Updated as of 11/19/16
    """ Returns mode string based on sum of system input buses. """
    ## NO FLOATING INPUTS ALLOWED ##
    if system_sum == 0x00:
        status = "System in Standby"
    elif system_sum == 0x06:
        status = "System Initializing"
    elif system_sum == 0x1C:
        status = "Side 1 Running"
    elif system_sum == 0x31:
        status = "Side 2 Running"
    else:
        status = "NOTICE: Unknown Mode"
        
    return status

def percentCheck(currentTimeLabel, totalTimeLabel):
    # Updated 11/19/16
    """ 
    Used to update progress bar percents and accounts for spacer dashes "-",
    and occational divide by 0 via try except.
    """
    try:
        progPercent = float(currentTimeLabel) / float(totalTimeLabel) * 100
    except (ValueError , ZeroDivisionError):
        progPercent = 0
        
    return progPercent
    
def resetGUI(self):
    # Updated 11/19/16
    """ Function to reset GUI for non-running interaction and display """
    # enable alteration of times
    self.cb_init_time_min.setEnabled(True)
    self.cb_init_time_sec.setEnabled(True)
    
    self.cb_side1_time_min.setEnabled(True)
    self.cb_side1_time_sec.setEnabled(True)
    
    self.cb_side2_time_min.setEnabled(True)
    self.cb_side2_time_sec.setEnabled(True)
    
    self.cb_repeat_cycle.setEnabled(True) 
    
    # set current times and Cycle to "-"
    self.current_Init_Time.setText("-")
    self.current_Side_1_Time.setText("-")
    self.current_Side_2_Time.setText("-")
    self.current_Rep_Cycle.setText("-")
    
    # set total times to "-"
    self.Init_tot.setText("-")
    self.Side_1_tot.setText("-")
    self.Side_2_tot.setText("-")
    self.Rep_Cycle_tot.setText("-")

def returnStatus(value, option):
    # Updated 03/19/17
    """ Value will be pin read value, return string is displayed on GUI """
    # if else to account for open/closed device vs on/off device
    if option == 'open':
        on = "<font color='green'>Open</font>"
        off = "<font color='red'>Closed</font>"
    else:
        on = "<font color='green'>On</font>"
        off = "<font color='red'>Off</font>"
    
    if value:   
        status = on
    else:       
        status = off
        
    return status
    
def setGUI(self):
    # Updated 11/19/16
    """ 
    Function to set GUI for run time interaction (i.e. changes disabled)
    and compute/display total mode and cycle times 
    """
    # disable alteration of times
    self.cb_init_time_min.setEnabled(False)
    self.cb_init_time_sec.setEnabled(False)
    
    self.cb_side1_time_min.setEnabled(False)
    self.cb_side1_time_sec.setEnabled(False)
    
    self.cb_side2_time_min.setEnabled(False)
    self.cb_side2_time_sec.setEnabled(False)
    
    self.cb_repeat_cycle.setEnabled(False)
    
    # Set total times to correct number from combo box for use in cycle thread
    cumulative_time = 0         # place holder for cumulative progress bar time
    cycles_tot = self.cb_repeat_cycle.currentIndex()+1  # for multiplication
    
    # Get time from GUI combobox inputs as total seconds - initialize time
    init_time_str = convert_time(int(self.cb_init_time_min. currentIndex()), 
                                int(self.cb_init_time_sec.currentIndex()))
    # echo to GUI
    self.Init_tot.setText(init_time_str)
    # add to cumulative time
    cumulative_time += float(init_time_str)
    
    # Get time from GUI combobox inputs as total seconds - side 1 time
    side1_time_str = convert_time(int(self.cb_side1_time_min.currentIndex()), 
                                int(self.cb_side1_time_sec.currentIndex()))
    # echo to GUI
    self.Side_1_tot.setText(side1_time_str)
    # add to cumulative time
    cumulative_time += float(side1_time_str)*cycles_tot
    
    # Get time from GUI combobox inputs as total seconds - side 2 time
    side2_time_str = convert_time(int(self.cb_side2_time_min.currentIndex()), 
                                int(self.cb_side2_time_sec.currentIndex()))
    # echo to GUI
    self.Side_2_tot.setText(side2_time_str)
    # add to cumulative time
    cumulative_time += float(side2_time_str)*cycles_tot
    # set cumulative time to total time on GUI
    self.Rep_Cycle_tot.setText( str(cumulative_time))


''' LOG funcions '''   
# Updated Completely as of 12/17/16
def initializeLog(): 
    # Updated as of 12/17/16
    ''' Generate Log name based on current time and date + log_append '''
    logName = time.strftime("%Y.%m.%d_%H.%M.%S_")+log_append+'.csv'
    
    ''' Custom Header Creation '''
    # Specify Column Log names - Notice no spaces between commas on purpose for format
    colNames = ('Date[YYYY.MM.DD],Time[HH:MM:SS.ms],Log Number,'
    'FP101,FP102,FP103,'            # var 1-3
    'FV201,FV202,FV203,FV204,'      # var 4-7
    'EM201,EM202,'                  # var 8-9
    'Temp1,Temp2,pH')               # var 10-12

    # Create Csv file with custom header
    with open(cwd+"/logs/"+logName, 'w', newline='') as csvfile:
        
        customHeader = csv.writer(csvfile, delimiter=' ',
                                quotechar=' ', quoting=csv.QUOTE_MINIMAL)
        
        colNames = [colNames] 
        customHeader.writerow(colNames)
        
    ''' Configure Logging '''
    # Create Handler
    handler = logging.FileHandler(cwd+"/logs/"+logName)  # sets where log is to be written
    handler.setLevel(logging.INFO)          # sets level of logs to collect
    
    # Create a logging format
    # Notice the removed space before %H to prevent auto format of csv
    # This causes hours to display wong in excel however, logged data is correct
    formatter = logging.Formatter(fmt='%(asctime)s.%(msecs)d,%(message)s', 
                   datefmt="%Y.%m.%d,%H:%M:%S")
                   
    # Set format to handler
    handler.setFormatter(formatter)
    
    # In order to account for multiple logging runs per session:
    # add handler to logger, remove old handler if not first_run
    if first_run.empty():   ## first_run == 0
        logger.removeHandler(logger.handlers[0])    # clear previous handler
        logger.addHandler(handler)                  # add new handler
    else: ## first_run == 1
        logger.addHandler(handler)
        first_run.get() # Remove first_run Flag
    
def printLog(parent, threadName, logRun):   #modified from multithread_02
    # Updated as of 12/28/16
    
    # To use global variables instead of locals
    global var1, var2, var3, var4, var5, var6, var7, var8, var9, var10
    global var11, var12
    
    ndx = 1                     # Used as a counter
    time_start = time.time()    # for initial cycle time
    ## logRun passed in as 1
    while logRun:               # will exit on 0
        
        if not log_q.empty():   ## log_q == 1
        
            if log_q.get():     # if number is not 0, clear queue and stop log
                logRun = 0      ## breaks out of outer while loop
            print("(exitFlag True, logRun == 0)")
            continue
            
        '''
        This is where values to be loggged are gathered.
        Place holder function calls for getTemp and getpH are here.
        Also creates log string written to csv log.
        '''
        
        # Get Current Bus Values
        current_bus_A = I2C.read_byte_data(In_bus, pinIn_A) # bus with valves
        current_bus_B = I2C.read_byte_data(In_bus, pinIn_B) # bus with pumps + magnets
        
        # Extract individual device status 'and True' required for 1 or 0
        var1 = int( (current_bus_B & FP101) and True )
        var2 = int( (current_bus_B & FP102) and True )
        var3 = int( (current_bus_B & FP103) and True )
        
        var4 = int( (current_bus_A & FV201) and True )
        var5 = int( (current_bus_A & FV202) and True )
        var6 = int( (current_bus_A & FV203) and True )
        var7 = int( (current_bus_A & FV204) and True )
        
        var8 = int( (current_bus_B & EM201) and True )
        var9 = int( (current_bus_B & EM202) and True )

        if ADC_DEBUG: ## for random 
            var10 = getTemp()
            var11 = getTemp()
        else:
            # place for temperature calls
            Vcc  = round( get_V(0, 2/3, data_rate, 6.144, num_to_avg), 4)  # Settings to read Vcc A_in_0
            Vadc_1 = round( get_V(1, 1, data_rate, 4.096, num_to_avg), 4)  # Settings to read A_in_1
            var10 = round( calc_temp(Vcc,  Vadc_1, Rs_1),  3)     
            
            Vcc  = round( get_V(0, 2/3, data_rate, 6.144, num_to_avg), 4)  # Settings to read Vcc A_in_0
            Vadc_2 = round( get_V(2, 1, data_rate, 4.096, num_to_avg), 4)  # Settings to read A_in_2
            var11 = round( calc_temp(Vcc,  Vadc_2, Rs_2),  3)   
    
 
        if PH_DEBUG: ## for random
            var12 = getpH()
        else:
            OS214.write(b'GETMEAS\r\n') 	# Sending command to have device send current measurement
            x=OS214.readline()
    
            while (sys.getsizeof(x) < 80):  # Checks for relevant data size
                x = OS214.readline()
        
            xstr= str(x)					# required type casting for split command
            parsed = xstr.split(",")	    # parse data

            #print (x) # NOTE:  Debug  # raw data print
            print("Parsed pH:  ", parsed[8])    # 8 == the desired data field
            var12 = float(parsed[8])
            
        # Create String To Log consisting of ndx plus 12 vars.
        logger.info('%d,%d,%d,%d,%d,%d,'
                    '%d,%d,%d,%d,%f,%f,%f',
                    ndx,var1,var2,var3,var4,var5,
                    var6,var7,var8,var9,var10,var11,var12)
                    
        print("*log %d logged" % ndx)           # status print for debug
        
        # wait for an exact time so log had reduced jitter
        tot_time = time.time() - time_start
        
        #print('log time: ', tot_time) # debug # TODO:  optimize with sampling...
        ##  More accurate sleep time and check if log taking too long.
        if tot_time > log_interval :
            print('Log taking longer than log interval to make...')
            print('total time:  %f' % tot_time)
        else:
            time.sleep(log_interval-tot_time)
            
        ndx += 1
        time_start = time.time()    #for complete loop process timing

''' GUI MainWindow class '''
# Updated 11/19/16
class MainWindow(QMainWindow, Ui_MainWindow):
    # Updated 11/19/16
    """
    Main GUI that will take user input for cycle times, display current system
    status and most recently logged temperature and pH
    """
    def __init__(self, parent=None):
        """ Automatically generated
        Constructor
        
        @param parent reference to the parent widget
        @type QWidget
        """
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        
        self.setWindowTitle("RPI HMI - pH Debug")     # Title creation
        

    def closeEvent(self, event):
        # Updated 12/28/16
        '''  Tasks to carry out if 'X' clicked '''
        systemOff()         # puts system into standby mode

        if not run_q.empty():
            run_q.get()         # remove item from run_q
            
        if log_q.empty():
            log_q.put(1)        # putting something in log_q stops loggings

        time_now = 0; time_start = time.time();
        while time_now < log_interval*2:
            self.System_Mode.setText("Shutting Down...")
            time_now = time.time()-time_start
            QApplication.processEvents()    # forces update of GUI?
            
        event.accept()
        
    @Slot()
    def on_start_btn_released(self):
        # Updated 11/19/16
        """
        On Start btn press :
            if run_q is empty
                disable alteration of cycle times via setGUI
                put 1 in run_q to signify running
                display system status as started
                create and start the logging thread
                create and start the mode thread that will take the times entered
                in on GUI as parameters.
                
            else: run_q has something in it -> already running
        """

        if run_q.empty():
            
            setGUI(self)
            run_q.put(1)
            self.System_Mode.setText("Started")
            
            log_thread = logThread(self, 1, "Logging Thread")
            log_thread.setDaemon(True)  # Stops thread if main thread stopped
            log_thread.start()
            
            cycle_thread = cycleThread(self, 2, "Mode Cycle Thread")
            cycle_thread.setDaemon(True)
            cycle_thread.start()
            
        else:   # run_q has something in it ->
            self.System_Mode.setText("Already Running")
    
    @Slot()
    def on_stop_btn_released(self):
        # Updated 11/19/16
        """ 
        on stop btn press:
            if running:
                removed running flag from run_q
                turn system to off/standy state
                sleep so log can reflect off state
                stop log by putting 1 in log_q
                reset GPIO pins to default state
                change systems status on GUI to standby
                reset GUI
            else: (already stopped)
                change system status to reflect already stopped   
        """
        if not run_q.empty():   # if run_q has something in it
            run_q.get()         # remove item from run_q
            systemOff()
            
            time.sleep(log_interval)   # wait for system to be shown in off state for 1 sec
            log_q.put(1)        # putting something in log_q stops loggings
            
            self.System_Mode.setText("System Stopped")
            
            resetGUI(self) 
            
        else: # run_q already empty ->system stopped
            self.System_Mode.setText("System Already Stopped")
            systemOff() # for double stop...
    
    @Slot(str)
    def on_system_time_textChanged(self, p0):
        # Updated 12/28/16
        """
        Slot designed to update progress bars from main GUI thread -for safety.  
        Will update every wait update interval as slot signaled in runMode function.
        """
        time_start = time.time()
        
        self.Init_prog.setValue( percentCheck(self.current_Init_Time.text(), self.Init_tot.text()) ) 
        self.Side_1_prog.setValue( percentCheck(self.current_Side_1_Time.text(), self.Side_1_tot.text()) ) 
        self.Side_2_prog.setValue( percentCheck(self.current_Side_2_Time.text(), self.Side_2_tot.text()) ) 
        self.Total_prog.setValue( percentCheck(self.current_Rep_Cycle.text(), self.Rep_Cycle_tot.text()) ) 
        
        # Get Current Bus Values For Mode Discovery
        current_bus_A = I2C.read_byte_data(In_bus, pinIn_A) # bus with valves
        current_bus_B = I2C.read_byte_data(In_bus, pinIn_B) # bus with pumps + magnets
        self.System_Mode.setText( disoverMode( current_bus_A + current_bus_B ) )
        
        # update top GUI info field
        self.as_of_time.setText("System Status as of "+ time.strftime("%B %d, %Y at %H:%M:%S"))
        
        # update individual device status on GUI
        self.FP101_val.setText( returnStatus(var1, 0) )
        self.FP102_val.setText( returnStatus(var2, 0) )
        self.FP103_val.setText( returnStatus(var3, 0) )
        
        self.FV201_val.setText( returnStatus(var4, 'open') )
        self.FV202_val.setText( returnStatus(var5, 'open') )
        self.FV203_val.setText( returnStatus(var6, 'open') )
        self.FV204_val.setText( returnStatus(var7, 'open') )
        
        self.EM201_val.setText( returnStatus(var8, 0) )
        self.EM202_val.setText( returnStatus(var9, 0) )

        # update Temperatures
        tempString = str(var10)
        self.temp_val_1.setText(tempString[0:4])

        tempString = str(var11)
        self.temp_val_2.setText(tempString[0:4])

        # update pH
        pHString = str(var12)
        self.pH_val.setText(pHString[0:6])
        
        if (time.time()-time_start > update_GUI_interval):
            print("GUI update longer than update interval...")
            
# (C) 2016-2017 Thad Haines
