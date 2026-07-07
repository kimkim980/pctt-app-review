import pandas as pd
from pathlib import Path
from src.deterministic_engine import analyze_structured_files

def main():
    p = Path('sample_test.xlsx')
    df = pd.DataFrame([
        {'Mã trạm':'BTS001','Ưu tiên':'UT1','Ém quân':'','Ngập':'Có','Chia cắt':'Không','ATS':'Có','PA CMN':'3','TGX':'1','Khoảng cách':'40'},
        {'Mã trạm':'BTS002','Ưu tiên':'UT2','Ém quân':'Nguyen Van A 09xxx','Ngập':'Không','Chia cắt':'Không','ATS':'','PA CMN':'1','TGX':'4','Khoảng cách':'10'},
    ])
    df.to_excel(p, index=False)
    result = analyze_structured_files([str(p)])
    print(result['summary'])
    for c in result['checks']:
        print(c['result'], c['severity'], c['rule_name'])
    p.unlink()

if __name__ == '__main__':
    main()
