'''
Generate datapoint object CSV for import
'''
import itertools
import csv

SYS = 'sdku'
DPT = 'ZDV'
DSC = ['КП ', ' Задв.']
PATTERN = ['A_KP_', '_ZDV_']
COUNT = [3, 10]
START = [1, 1]
FOLDER_OUT = 'ref/in/'


def generate(sys=SYS, dpt=DPT, dsc=DSC, pattern=PATTERN,
             count=COUNT, start=START):
    ranges = [range(start[i], start[i] + count[i])
              for i in range(len(pattern))]

    names = [
        ''.join(f'{pattern[i]}{num}' for i, num in enumerate(nums))
        for nums in itertools.product(*ranges)
    ]
    dscs = [
        ''.join(f'{dsc[i]}{num}' for i, num in enumerate(nums))
        for nums in itertools.product(*ranges)
    ]

    fname = f'{FOLDER_OUT}dp_.csv'
    with open(fname, 'w', encoding='utf-8', newline='\n') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['id', 'sys', 'dpt', 'name', 'dsc', 'disable'])
        for idx, name in enumerate(names):
            writer.writerow([idx, sys, dpt, name, dscs[idx], ''])
    return len(names)


if __name__ == '__main__':
    cnt = generate()
    print(f'Generated {cnt} objects')
