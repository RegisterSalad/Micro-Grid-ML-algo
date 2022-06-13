import csv
import ast #Library for parsing formula syntax
import operator as op
from math import e
import re

# supported operators
operators = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
             ast.Div: op.truediv, ast.Pow: op.pow, ast.BitXor: op.xor,
             ast.USub: op.neg}

def eval_expr(expr):
    if expr != '':
        return eval_(ast.parse(expr, mode='eval').body)
    else:
        return None

def eval_(node):
    if isinstance(node, ast.Num): # <number>
        return node.n
    elif isinstance(node, ast.BinOp): # <left> <operator> <right>
        return operators[type(node.op)](float(eval_(node.left)), float(eval_(node.right)))
    elif isinstance(node, ast.UnaryOp): # <operator> <operand> e.g., -1
        return operators[type(node.op)](eval_(node.operand))
    else:
        raise TypeError(node)

class StorageSuite:
    def __init__(self, filename):
        self.device_data = {}
        self.storage_suite = {}
        with open(filename, newline='', encoding='utf-8-sig') as devices_file:
            reader = csv.DictReader(devices_file)
            for row in reader:
                self.device_data[row['type']] = row
        for device in self.device_data:
            self.storage_suite[device] = Storage(data=self.data.device_data[device], type=device)

    def modify_ss(self, param: dict):
        for device in self.storage_suite:
            self.storage_suite[device].modify(param[device])

# StorageSuite
# Inputs:
#   param: a dict(device->dict(parameter->value)) where
#       - the parent dict's keys are each device (str) in data, the value of each is a
#       - dict of parameter (i.e. cap, or power if applicable) to its value

# Wondering if a StorageSuite class is needed or if this can just be implemented within the code.
# I'll have to think about this.
# To avoid excessive RAM usage, might reuse Storage classes between microgrids and just overwrite them
# - could just write their data/parameters to a text file before moving on to the next microgrid

#string.replace(old, new) (immutable) [replace() syntax]

# need to account for some types 

# v2g is going to have to have unit capacity multiplied by number of houses
# probably similar to how PV generation is determined



class Storage:
    def __init__(self, data: dict, type: str, cap: float, power: float = None, start_window: int = None, end_window: int = None):
        
        
        #fixed
        self.DATA = data
        self.TYPE = type
        self.cap = cap # in kWh
        self.power = power # in kW
        if self.power == None:
            self.power = cap * eval_expr(self.data['max_cont_discharge']) # uses default power to capacity ratio for given type
        self.START_WINDOW = start_window # start time that device can be used (V2G), in seconds of the day out of 86,400
        self.END_WINDOW = end_window # end time that device can be used (V2G), in seconds of the day out of 86,400
    
        self.MAX_SOC = data['max_charge'] # maximum charge as a proportion of capacity
        self.MIN_SOC = data['min_charge'] # minimum charge as a proportion of capacity
        self.max_soc_cap = data['max_charge'] * cap # maximum charge in kWh
        self.min_soc_cap = data['min_charge'] * cap # minimum charge in kWh
        #self.MAX_CHARGE_RATE = ss.device_data['max_charge_rate'] * 
        #self.MIN_CHARGE_RATE = ss.device_data['min_charge_rate']
        #self.MAX_CONT_DISCHARGE = ss.device_data['max_cont_discharge'] 
        
        #self.MIN_DISCHARGE = ss.device_data['min_discharge'] * cap

     
        #calculated
        self.PEAK_DISCHARGE = eval_expr(data['max_peak_discharge'].replace("x", str(self.power))) * self.power # assumed 10s peak capability, in kW
        self.FORMULA_EFF_CHARGE = data['eff_charge'].replace("x", "self.soc")
        
        # may need to adjust formulae in current CSV to take proportional SOC rather than current_charge
        # would just have to divide each x in the formula by the capacity of the flywheel used for modelling, probably 29kWh
        self.FORMULA_EFF_DISCHARGE = data['eff_discharge'].replace("x", "self.soc").replace("'", "")
        
        self.FORMULA_SELF_DISCHARGE = data['self_discharge'].replace("x", "self.soc").replace("'", "") # where x is SoC
        

        self.FORMULA_CAPITAL_COST = data['capital_cost']
        def capital_cost(): # independent capacity and power capital cost formula
            return eval_expr(self.FORMULA_CAPITAL_COST.replace("x", str(self.cap)).replace("y", str(self.power)).replace("'", "")) * self.cap

        if bool(data['cap_power_ind']):
            self.capital_cost = capital_cost() # if capital cost is a function of both power and capacity, in USD
        else:
            self.capital_cost = data['capital_cost'] * cap # if capital cost is primarily a function of capacity only, in USD

        self.MARGINAL_COST = data['marginal_cost'] # cost to use device per kW in/out, in USD
        #self.ramp_speed = ss.device_data['ramp_speed']
        self.resp_time = data['resp_time'] # time it takes for device to realize command, in seconds
        self.soc = 0.85 # state of charge as a proportion of capacity
        self.soc_cap = self.soc * self.cap # state of charge in kWh

        #user/AI-defined
        pass

    def self_discharge(self): # self-discharge rate, in SOC/s
        return eval_expr(self.FORMULA_SELF_DISCHARGE.replace("self.soc", str(self.soc)).replace("e", str(e)))
        #parsed_expr = ast.parse(self.FORMULA_SELF_DISCHARGE.replace("self.soc", str(self.soc)).replace("e", str(e)))
        #return ast.literal_eval(parsed_expr)
    def eff_charge(self): # charge effiency function
        return eval_expr(self.FORMULA_EFF_CHARGE.replace("self.soc", str(self.soc)).replace("'", ""))
    def eff_discharge(self): # discharge effiency function
        return eval_expr(self.FORMULA_EFF_DISCHARGE.replace("self.soc", str(self.soc)))
    def current_charge(self):
        return self.soc * self.cap
    
    def modify(self, param: dict):
        self.cap = param['cap']
        if 'power' in param:
            self.power = param['power']
        else:
            self.power = self.cap * eval_expr(self.data['max_cont_discharge'])
        self.max_soc_cap = self.data['max_charge'] * self.cap
        self.min_soc_cap = self.data['min_charge'] * self.cap
        if bool(self.data['cap_power_ind']):
            self.capital_cost = self.capital_cost()
        else:
            self.capital_cost = self.data['capital_cost'] * self.cap
            # should streamline this so it's just a formula regardless of linear proportionality

    def print_properties(self):
        print("**************************\n")
        print("Device: " + self.TYPE)
        for prop in self.DATA:
            print(prop + ": " + self.DATA[prop] + "\n")

    def print_variables(self):
        print("**************************\n")
        print("Device: " + self.TYPE + "\n")
        print("Capacity: " + self.cap + "kWh\n")
        print("Power: " + self.power + "kW\n")
        

if __name__ == "__main__":
    test_ss = StorageSuite('data/energy_storage_devices_v5.csv')
    print(test_ss.storage_suite['li-ion'].self_discharge())
    print(test_ss.storage_suite['li-ion'].CAPITAL_COST)
    print(test_ss.storage_suite['li-ion'].eff_charge())
    print(test_ss.storage_suite['li-ion'].eff_discharge())
    print(test_ss.storage_suite['li-ion'].current_charge())

    #print(test_ss.device_data)
    #print(test_ss.storage_suite['flywheel'].CAPITAL_COST)
    #print(test_ss.device_data['flywheel']['capital_cost'])



#do we need to include response time of aggregator?
#maybe we can have aggegator control as a boolean
#or even separate suites for each?

# NEXT STEPS:
# 1. Check that formulae are normalized rather than correpsonding to specific caps, powers, or other attributes
# 2. Research aggregator response time