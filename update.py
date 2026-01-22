# 更新依赖.py  —— 运行不了主程序时，双击这个就行
import os, sys
print("正在更新 huggingface_hub（只需要点一次）...")
os.system(f'"{sys.executable}" -m pip install --upgrade huggingface_hub')
print("\n更新完成！现在可以正常使用主程序了")
input("按回车关闭...")