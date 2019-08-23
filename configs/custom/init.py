# Copyright (c) 2015 ARM Limited
# All rights reserved.
#
# The license below extends only to copyright in the software and shall
# not be construed as granting a license to any other intellectual
# property including but not limited to intellectual property relating
# to a hardware implementation of the functionality of the software
# licensed hereunder.  You may use the software subject to the license
# terms below provided that you ensure that this notice is replicated
# unmodified and in its entirety in all distributions of the software,
# modified or unmodified, in source code or in binary form.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Authors: Radhika Jagtap

# Basic elastic traces replay script that configures a Trace CPU

from __future__ import print_function
from __future__ import absolute_import

import optparse

from m5.util import addToPath, fatal

addToPath('../')

from common import Options
from common import Simulation
from common import CacheConfig
from common import MemConfig
from common.Caches import *

parser = optparse.OptionParser()
Options.addCommonOptions(parser)

if '--ruby' in sys.argv:
    print("This script does not support Ruby configuration, mainly"
    " because Trace CPU has been tested only with classic memory system")
    sys.exit(1)

# Add an option to get the cache specification file
parser.add_option('--cache-specs-file', help="Path to JSON file with the "\
                    "specifications for all caches in custom hierarchy")

(options, args) = parser.parse_args()

if args:
    print("Error: script doesn't take any positional arguments")
    sys.exit(1)

numThreads = 1

if options.cpu_type != "TraceCPU":
    fatal("This is a script for elastic trace replay simulation, use "\
            "--cpu-type=TraceCPU\n");

if options.num_cpus > 1:
    fatal("This script does not support multi-processor trace replay.\n")

# In this case FutureClass will be None as there is not fast forwarding or
# switching
(CPUClass, test_mem_mode, FutureClass) = Simulation.setCPUClass(options)
CPUClass.numThreads = numThreads

system = System(cpu = CPUClass(cpu_id=0),
                mem_mode = test_mem_mode,
                mem_ranges = [AddrRange(options.mem_size)],
                cache_line_size = options.cacheline_size)

# Create a top-level voltage domain
system.voltage_domain = VoltageDomain(voltage = options.sys_voltage)

# Create a source clock for the system. This is used as the clock period for
# xbar and memory
system.clk_domain = SrcClockDomain(clock =  options.sys_clock,
                                   voltage_domain = system.voltage_domain)

# Create a CPU voltage domain
system.cpu_voltage_domain = VoltageDomain()

# Create a separate clock domain for the CPUs. In case of Trace CPUs this clock
# is actually used only by the caches connected to the CPU.
system.cpu_clk_domain = SrcClockDomain(clock = options.cpu_clock,
                                       voltage_domain =
                                       system.cpu_voltage_domain)

# All cpus belong to a common cpu_clk_domain, therefore running at a common
# frequency.
for cpu in system.cpu:
    cpu.clk_domain = system.cpu_clk_domain

# BaseCPU no longer has default values for the BaseCPU.isa
# createThreads() is needed to fill in the cpu.isa
for cpu in system.cpu:
    cpu.createThreads()

# Assign input trace files to the Trace CPU
system.cpu.instTraceFile=options.inst_trace_file
system.cpu.dataTraceFile=options.data_trace_file


# Configure the classic memory system options
MemClass = Simulation.setMemClass(options)
system.membus = SystemXBar()
system.system_port = system.membus.slave


#### Deepraj's Addition ####

import yaml

if not options.cache_specs_file.endswith('.json'):
    fatal("init.py expects a JSON file with cache configuration "\
            "information for the entire hierarchy")

with open(options.cache_specs_file, "r") as cconfig:
    cc_inp = yaml.safe_load(cconfig)

levels = cc_inp['num_levels']
# only if we need any caches
if levels != 0:
    # some sanity check
    # 'caches' is an array of configurations for each level
    # size should be 1 more than levels because of L1I and L1D caches
    if cc_inp['caches'][0]['type'] != 'L1I':
        print("First configuration has to be of L1I.\n")
        sys.exit(1)
    if cc_inp['caches'][1]['type'] != 'L1D':
        print("Second configuration has to be of L1D.\n")
        sys.exit(1)
    if levels+1 != len(cc_inp['caches']):
        print("Check the number of configurations provided for the "\
                "given number of levels.\n")
        sys.exit(1)
    else:
        print("Reading configuration file")
    curr_type_num = 0
    proto_l1 = Cache(size = '32kB', assoc = 4,
                 tag_latency = 1, data_latency = 1, response_latency = 1,
                 tgts_per_mshr = 8, clusivity = 'mostly_incl',
                 writeback_clean = True)
    cache_proto = [proto_l1]
    # to-do: add sanity checks for cache parameters
    for i, params in enumerate(cc_inp['caches']):
        # Make sure everything after L1D is in order of hierarchy
        if i>1:
            # throw an exception if it's L[num]letter. Only L[num]
            # is valid cache 'type'.
            try:
                curr_type_num = int(params['type'][1:len(params['type'])])
            except ValueError:
                print("Make sure 'type' name for", str(params['type']),\
                         "cache follows the naming convention L[num] and"\
                         " there are no letters after level number.\n")
                sys.exit(1)
            # if the configuration is out of place in hierarchy
            if i != curr_type_num:
                print("Config", i, "is out of place. Make sure",\
                        params['type'], "cache is in the correct place "\
                        "in the hierarchy.")
                sys.exit(1)
        cc = Cache(size = params['size'], assoc = params['assoc'],
                   tag_latency = params['tag_latency'],
                   data_latency = params['data_latency'],
                   response_latency = params['response_latency'],
                   mshrs = params['mshrs'],
                   tgts_per_mshr = params['tgts_per_mshr'],
                   clusivity = params['clusivity'],
                   writeback_clean = params['writeback_clean'])
        cache_proto.insert(i, cc)

    # Connect icache and dcache
    system.cpu.icache = cache_proto[0]
    system.cpu.dcache = cache_proto[1]
    # Connect the instruction and data caches to the CPU
    system.cpu.icache_port = system.cpu.icache.cpu_side
    system.cpu.dcache_port = system.cpu.dcache.cpu_side

    system.l2bus = L2XBar()

    # setup the subsystems (iff we have L2+ caches)
    if levels > 1:
        # L1I and L1D are the first two caches in cache_proto[]
        # L2+ will be there at indices 2 until levels+1
        # (there are levels+1 caches in cache_proto)
        for curr_level in range(2, levels+1):
            # setup a subsystem for every cache level
            subsys = SubSystem()
            setattr(system, 'l%dsubsys' % curr_level, subsys)

            # create the crossbar for this level
            subsys.xbar = L2XBar()
            # if curr_level is not the last level
            if curr_level != levels:
                next_cache = cache_proto[curr_level+1]
                # connect this crossbar to the next cache's receiving port
                subsys.xbar.master = next_cache.cpu_side
            # this level cache setup
            subsys.cache = cache_proto[curr_level]
            subsys.cache.mem_side = subsys.xbar.slave
            if curr_level == 2:
                system.l2bus.master = subsys.cache.cpu_side
        # connect L1 cache memory_side to L2bus & to L2cache
        L2_subsys = getattr(system, 'l2subsys')
        system.cpu.icache.mem_side = system.l2bus.slave
        system.cpu.dcache.mem_side = system.l2bus.slave

        # connect llc to memory bus
        llc_subsys = getattr(system, 'l%dsubsys' % levels)
        llc_subsys.xbar.master = system.membus.slave

    elif levels == 1:
        # if there's only L1 cache, connect it to memory bus
        system.cpu.icache.mem_side = system.membus.slave
        system.cpu.dcache.mem_side = system.membus.slave
    else:
        fault("Variable levels is set to 0 in cache_config.json but "\
                "control is inside a section that is meant for "\
                "non-zero values of `levels`.\n"\
                "Check configuration script for gem5.")

'''
TODO: handle no-cache case (levels == 0)
'''
# if there are no caches (levels is set to 0), no need to check for configs
# connect icache and dcache ports of the cpu to the memory bus
if levels == 0:
    system.cpu.icache_port = system.membus.slave
    system.cpu.dcache_port = system.membus.slave



system.cpu[0].createInterruptController()
MemConfig.config_mem(options, system)

root = Root(full_system = False, system = system)
Simulation.run(options, root, system, FutureClass)

