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

State Process
-------------
The state process is a program that is continually executed. When its execution is over, the execution starts again.

The state process information is stored under `self.process.state`. You can retrieve the name and arguments of the current state process by using `self.process.state.name` and `self.process.state.args` respectively.


Instructions
------------
Instructions are the basic building block of programs. They are made of Lua code. Their name is usually of the syntax <namespace>:<instruction name>, but after "namespace" there could be more names which actually represent grouping. These are merely conventions and are not really needed - the name is just the name and is not used by `anpc` in any way. Instructions can receive an arbitrary number of parameters. Some instructions are built-in (and these are named always with "npc" as the namespace) while others can be registered locally.


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

### Scheduling
Scheduled interrupts let a program fire when the in-game clock enters a
time window. All times are on the game-clock scale of `@time`: 0..23999,
one day = 24000 (1 tick = 1 in-game minute). The engine checks the
schedule every process step; a firing entry is *preemptive* by default
(it interrupts the running program, which resumes afterwards).

* `npc:schedule:add`
  * Adds a schedule entry and returns its id (use it with `npc:schedule:remove` / `npc:schedule:trigger`). The entry fires when the game clock enters the `[earliest, latest)` window (the window may wrap midnight, e.g. `earliest = 20000, latest = 6000`).
  * Arguments:
    * `program`: *string*. Name of the program to run when the entry fires. Must be registered (by fire time; a warning is logged at add time if it isn't).
    * `args`: *table*. Optional arguments passed to the program.
    * `earliest`: *number*. Start of the firing window. Default 0.
    * `latest`: *number*. End of the firing window (exclusive). If smaller than `earliest`, the window wraps midnight. Default 24000 (whole day).
    * `recurrency`: *string*. `"daily"` (re-arm the entry every day, default) or `"none"` (fire once, then the entry is done).
    * `repeat_interval`: *number*. Game-clock time between repeats inside the window (e.g. 2000 = every ~50 in-game minutes). If omitted, the entry fires at most once per day.
    * `end_time`: *number*. Game-clock time after which repeats stop (only enforced for non-wrapping windows).
    * `preemption`: *string*. `"park"` (default) interrupts the running one-shot program - it stays parked in the queue and resumes at the same instruction after the scheduled program finishes; `"tail"` runs the program after everything currently pending; `"replace"` drops pending one-shots and runs it immediately.
* `npc:schedule:remove`
  * Removes a schedule entry. Returns `false` for unknown ids and for entries whose program is currently running.
  * Arguments:
    * `entry_id`: *number*. Id returned by `npc:schedule:add`.
* `npc:schedule:trigger`
  * Forces an entry to fire immediately, bypassing the window check (also re-arms `"done"` entries). Useful for testing and for "do it now" behavior.
  * Arguments:
    * `entry_id`: *number*. Id returned by `npc:schedule:add`.

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
    

