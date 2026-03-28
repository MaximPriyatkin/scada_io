'''
generate object 
'''

import itertools
import common as cm

DSC = ['КП ', ' Задв.']
PATTERN = ['A_KP_', '_ZDV_']
COUNT = [3, 10]
START = [1, 1]
SYS = 'sdku'
DPT = 'ZDV'

ranges = [range(START[i], START[i]+COUNT[i]) 
                for i in range(len(PATTERN))]

names = [
    ''.join(f'{PATTERN[i]}{num}' for i, num in enumerate(nums))
    for nums in itertools.product(*ranges)
]

dscs = [
    ''.join(f'{DSC[i]}{num}' for i, num in enumerate(nums))
    for nums in itertools.product(*ranges)    
]

cnt = 0
out = 'id	sys	dpt	name	dsc	disable\n'
for idx, name in enumerate(names):
    out = f'{out}{cnt}\t{SYS}\t{DPT}\t{name}\t{dscs[idx]}\n'
    cnt += 1
fname = 'ref/in/dp_.csv'
#with open(fname, 'w', encoding='utf-8', newline='\n') as f:
#    f.write(out)



