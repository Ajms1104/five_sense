import pandas as pd
import os
import numpy as np

# 확인할 파일 경로 리스트
files_to_check = {
    "Train": "preprocessed_dfs/train_df_scaled.pkl",
    "Validation": "preprocessed_dfs/val_df_scaled.pkl",
    "Test": "preprocessed_dfs/test_df_scaled.pkl"
}

print("="*40)
print("preprocessed_dfs 폴더의 3개 파일 스캔 중...")
print("="*40)

all_found = True

for name, path in files_to_check.items():
    
    print(f"\n--- {name} Set ---")
    
    if not os.path.exists(path):
        print(f"❌ 파일이 존재하지 않습니다: {path}")
        all_found = False
        continue
    
    try:
        df = pd.read_pickle(path)
        
        if df.empty:
            print(f"✅ 파일은 존재하지만 비어있습니다 (0건).")
            print(f"   Shape: {df.shape}")
        else:
            print(f"⭐️ 데이터가 있습니다 ({len(df)} 건).")
            print(f"   Shape: {df.shape}")
            
            # 'direction' (타겟) 비율 확인
            if 'direction' in df.columns:
                try:
                    pos_count = df['direction'].sum()
                    total_count = len(df)
                    pos_rate = (pos_count / total_count) if total_count > 0 else 0
                    
                    print(f"   Direction (1s) 비율: {pos_rate:.4f} ({pos_count} / {total_count})")
                except Exception as e:
                    print(f"   'direction' 비율 계산 중 오류: {e}")
            else:
                print(f"   ⚠️ 'direction' 컬럼이 없어 비율을 계산할 수 없습니다.")
                
    except Exception as e:
        print(f"❌ 파일을 읽는 중 오류 발생: {e}")
        all_found = False

print("\n" + "="*40)
if all_found and not pd.read_pickle(files_to_check["Test"]).empty:
     print("결론: Train, Val, Test 셋이 모두 존재합니다.")
     print("(phase0 실행 시 split_mode='fixed' 또는 'auto' 였습니다.)")
elif all_found:
    print("결론: Train, Val 셋은 있으나 Test 셋이 비어있습니다.")
    print("(phase0 실행 시 split_mode='walkforward' 였습니다.)")
else:
    print("결론: 일부 .pkl 파일이 누락되었거나 읽을 수 없습니다.")
