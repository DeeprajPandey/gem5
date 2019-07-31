import m5
from m5.objects import *

system = System()

# create a clock doamin and set frequency at 1GHz
# voltage set to defaults
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = '1GHz'
system.clk_domain.voltage_domain = VoltageDomain()

# set up memory
system.mem_mode = 'timing'
system.mem_ranges = [AddrRange('512MB')]

# cpu
system.cpu = DerivO3CPU()

system.membus = SystemXBar()

# no caches: connect I-cache and D-cache to membus
system.cpu.icache_port = system.membus.slave
system.cpu.dcache_port = system.membus.slave

system.cpu.createInterruptController()

# DDR3 memory controller
system.mem_ctrl = DDR3_1600_8x8()
system.mem_ctrl.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.master

# system connects to the membus
system.system_port = system.membus.slave

# create a process
process = Process()
process.cmd = ['tests/test-progs/hello/bin/arm/linux/hello']

# cpu will have the process as its workload and create thread contexts
system.cpu.workload = process
system.cpu.createThreads()

# set up root object
root = Root(full_system = False, system = system)
m5.instantiate()

print("Starting simulation")
exit_event = m5.simulate()

print('Exiting @ tick %i because %s' % (m5.curTick(), exit_event.getCause()))

