# Me wrinting a minimalistic readme

This is a simple pulse library that is made to work together with the Keysight AWG. The main motivation for this library was to have a very easy and strucutred way to make waveforms. Als attention is given to performance so the constrution of the waveform should always be faster then upload time (challaging if you upload goes via pcie). Note that it is not the intention to support other systems with this project. 

Features now include:
* Native support for virtual gates
* support for any pulse and sine waves (phase coherent atm)
* Sequencing
* delay in aeg lines.

Todo list:
* Fully multidimensionlisation of the segment object (with matrix operators)
* Memory segmentation on the keysight awg. This will be needed if you want to upload during an experiment.
* faster add function for block funtion (now performace issues of more then ~2000 elements in a sequence (not nice to call a lot)).
* advanced (integrated) looping methods -- decorator approach + looping class. Support for calibarion arguments? -- this should be enegnneerd well.
* more base functions
	* e.g. (IQ toolkit and IQ virtual channels) -- IF IQ is key for high performance (for IQ offset).
	* Normal channels phase coherennt or not??
* support for memory segmentation for the keysight -- upload during experiment capelibility

Below are some basic commands that show how the library works. 
Create a pulse object. You should do this in the station
```python

	p = pulselib()
```

Now one can define segments,
```python

	seg  = p.mk_segment('INIT')
	seg2 = p.mk_segment('Manip')
	seg3 = p.mk_segment('Readout')
```
A core idea of the package is that all the segments in the sefgment object have the same lenght.

Then to each segments you can add some basic waveform. Here you are free to add anything you want. 
Some examples follow (times are by default in ns).
```python
	seg.B0.add_pulse([[10,0],[10,5],[20,10],[20,0]]) # adds a linear ramp from 10 to 20 ns with amplitude of 5 to 10.
	# B0 is the barrier 0 channel
	seg.B0.add_block(40,70,2) # add a block pulse of 2V from 40 to 70 ns, to whaterver waveform is already there
	seg.B0.wait(50)#just waits (e.g. you want to ake a segment 50 ns longer)
	seg.B0.reset_time(). #resets time back to zero in segment. Al the commannds we ran before will get a negative time. 
```

One pulses are added, you can define like:
```python
	SEQ = [['INIT', 1, 0], ['Manip', 1, 0], ['Readout', 1, 0] ]
```

Which can next be added to the pulse object and next be uploaded.
```python
	p.add_sequence('mysequence', SEQ)

	p.start_sequence('mysequence')
```
Virtual gates are also supported. This can simply be done by definig:
```python
	awg_virtual_channels = {'virtual_gates_names_virt' : ['vP1','vP2','vP3','vP4','vP5','vB0','vB1','vB2','vB3','vB4','vB5'],
									 'virtual_gates_names_real' : ['P1','P2','P3','P4','P5','B0','B1','B2','B3','B4','B5'],
									 'virtual_gate_matrix' : np.eye(11)}
```
The virtual gates are simply acceible by calling seg.virtualchannelname
Note that thresolds are chosen automatically. Memory menagment is also taken care of for you  :)
