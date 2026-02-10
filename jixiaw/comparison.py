import json

def compare_jsonl(file1_path, file2_path):
    def load_data(filepath):
        data_map = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                item = json.loads(line)
                # 使用 (module, full_name) 作為唯一鍵
                key = (item.get('module'), item.get('full_name'))
                data_map[key] = item.get('tactic_proof', '')
        return data_map

    # 1. 讀取兩個檔案
    map1 = load_data(file1_path)
    map2 = load_data(file2_path)

    # 2. 獲取所有的鍵集合
    keys1 = set(map1.keys())
    keys2 = set(map2.keys())

    # 3. 執行邏輯比對
    only_in_1 = keys1 - keys2
    only_in_2 = keys2 - keys1
    common_keys = keys1 & keys2

    same_content = []
    diff_content = []

    for k in common_keys:
        if map1[k] == map2[k]:
            same_content.append(k)
        else:
            diff_content.append(k)

    # 4. 輔助函數：寫出結果
    def write_output(filename, keys, data_source_map):
        with open(filename, 'w', encoding='utf-8') as f:
            for k in sorted(keys):
                # 構建輸出格式
                out_item = {
                    "module": k[0],
                    "full_name": k[1],
                    "tactic_proof": data_source_map[k]
                }
                f.write(json.dumps(out_item, ensure_ascii=False) + '\n')

    # 5. 輸出四個檔案
    write_output('only_in_file1.jsonl', only_in_1, map1)
    write_output('only_in_file2.jsonl', only_in_2, map2)
    write_output('same.jsonl', same_content, map1)
    write_output('different.jsonl', diff_content, map2) # 這裡選擇存儲 file2 的版本

    print(f"比對完成！")
    print(f"- 僅在文件 1: {len(only_in_1)}")
    print(f"- 僅在文件 2: {len(only_in_2)}")
    print(f"- 內容完全相同: {len(same_content)}")
    print(f"- 內容不同: {len(diff_content)}")

# 使用範例
# compare_jsonl('file1.jsonl', 'file2.jsonl')
