import python_minifier, re

for file in ["uci", "usunfish_engine", "usunfish_gmv", "usunfish_common"]:

    with open(f'{file}.py', encoding="utf8") as f:
        compressed = f.read()
   
    compressed = python_minifier.minify(compressed, remove_literal_statements=True,
                                            rename_locals=True,
                                            hoist_literals=False, 
                                            rename_globals=False, 
                                            preserve_globals=["const","_A1","_H1", "_A8","_H8","_NO","_E","_S","_W","_P","_N","_B","_R","_Q","_K","_ep","_kp","_wc_bc"])
    with open(f'min/{file}.py', 'w') as f:
        f.write(compressed)
