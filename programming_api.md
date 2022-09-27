# Programming Reference for `anpc`
Anpcscript is the programming language for `anpc`. `anpc` takes the idea that NPCs are independent *beings*, able to move and interact with their environment (the Minetest world) in different ways, and over time (and sometimes, **only** over time!). In order for NPCs to execute tasks, `anpc` implements each NPC in a simplified OS-programming model. Therefore, each NPC has:
* Data storage
  * Global
  * For each process
  * Temporary
* A process queue
* Timers

Therefore, the main concept for creating NPCs with `anpc` are programs, which are created using an instruction set.

## Programs
Programs are made of three basic concepts:
1. Instructions
2. Program control
3. Variables

Instructions
------------
Instructions are the basic building block of programs. They are made of Lua code. Their name is usually of the syntax <namespace>:<instruction name>, but after "namespace" there could be more names which actually represent grouping. These are merely conventions and are not really needed - the name is just the name. Instructions can receive an arbitrary number of parameters. Some instructions are built-in (and these are named always with "npc" as the namespace) while others can be registered locally.

Instruction reference:
----------------------
This list is exhaustive of all built-in instructions supported.

### Core instructions
* `npc:execute`
  * Executes another program
  * Arguments:
    * `name`: *string*. Name of the program to be executed. Must be the name of any program that is registered with `npc.proc.register_program`
    * `args`: *table*. Arguments for the program
* `npc:wait`
  * Stop process execution for the desired time. This is not a busy wait, it instead changes the process interval in the right way.
  * Arguments:
    * `time`: *number*. The time to wait, in seconds. Decimal values are supported, but it should be taken into account that it should never be smaller than `dtime` (the server's step time). This is not validated.

### Utilities
* `npc:random`
  * Returns a random number in the given range. Same as Lua's `math.random`
  * Arguments:
    * `start`: *number*. The beginning of the range
    * `end`: *number*. The end of the range
* `npc:distance_to`
  * Returns the distance from the NPC to a given node or object
  * Arguments:
    * `pos`: *table, with x, y and z*. If given, will return the distance to the given position. Shouldn't be used together with `object`
    * `object`: *userdata*. If given, will return distance from NPC to given object at that time. Shouldn't be used together with `pos`
    * `round`: *boolean*. If given, will round distance value using `vector.round()`
    

