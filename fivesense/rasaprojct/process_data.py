from actions.data_processor import StockOptionsDataProcessor

def main():
    processor = StockOptionsDataProcessor()
    success = processor.process_and_store_data()
    
    if success:
        print("데이터 처리 및 저장이 성공적으로 완료되었습니다.")
    else:
        print("데이터 처리 중 오류가 발생했습니다.")

if __name__ == "__main__":
    main() 