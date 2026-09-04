import glob, os, re

# Tum Python dosyalarini topla
py_files = [f for f in glob.glob('*.py') if f.startswith('mod_') or f in ('main.py','app.py','app_flet.py','analiz.py','api.py','backtest.py','grafik.py','grafik_html.py','hisse_isimleri.py','hisseler_bist.py','hisseler_kripto.py','hisseler_nasdaq.py','hisseler_sp500.py','otomatik_tarayici.py')]
py_files.sort()

with open('_import_raporu.txt','w',encoding='utf-8') as r:
    r.write('=== PROJE IMPORT ILISKILERI ===\n')
    r.write(f'Toplam {len(py_files)} dosya tarandi\n\n')

    # Her dosyadaki import'lari bul
    all_imports = {}
    for f in py_files:
        with open(f, 'r', encoding='utf-8', errors='replace') as fh:
            content = fh.read()
        imports = re.findall(r'^from\s+(\S+)\s+import', content, re.MULTILINE)
        imports += re.findall(r'^import\s+(\S+)', content, re.MULTILINE)
        local_imports = [i for i in imports if i.startswith('mod_') or i in ['analiz','backtest','grafik','hisse_isimleri','hisseler_bist','hisseler_kripto','hisseler_nasdaq','hisseler_sp500','otomatik_tarayici']]
        all_imports[f] = local_imports

    r.write('DOSYALAR VE IMPORT EDILEN MODULLER\n\n')
    for f, imps in sorted(all_imports.items(), key=lambda x: -len(x[1])):
        r.write(f'  {f}:\n')
        if imps:
            for i in imps:
                r.write(f'    -> {i}\n')
        else:
            r.write('    (hicbir yerel modul import etmiyor)\n')
        r.write('\n')

    r.write('\nEKSIK BAGLANTI TARAMASI\n\n')
    eksikler = []
    for f, imps in all_imports.items():
        for i in imps:
            i_file = i if i.endswith('.py') else i + '.py'
            if i_file not in py_files:
                eksikler.append((f, i_file))

    if eksikler:
        for f, i in eksikler:
            r.write(f'  X {f} -> {i} DOSYASI BULUNAMADI!\n')
    else:
        r.write('  OK Tum import edilen modul dosyalari fiziksel olarak mevcut.\n')

    # Karsilikli bagimlilik (circular import) taramasi
    r.write('\nKARSILIKLI BAGIMLILIK (CIRCULAR IMPORT) TARAMASI\n\n')
    for f, imps in all_imports.items():
        for i in imps:
            i_file = i if i.endswith('.py') else i + '.py'
            if i_file in all_imports:
                i_imports = all_imports[i_file]
                for j in i_imports:
                    j_file = j if j.endswith('.py') else j + '.py'
                    if j_file == f:
                        r.write(f'  CIRCULAR: {f} <-> {i_file}\n')
                        break

    # En cok import edilen moduller
    r.write('\nEN COK IMPORT EDILEN MODULLER\n\n')
    import_counter = {}
    for f, imps in all_imports.items():
        for i in imps:
            import_counter[i] = import_counter.get(i, 0) + 1
    for mod, cnt in sorted(import_counter.items(), key=lambda x: -x[1]):
        r.write(f'  {mod}: {cnt} dosya tarafindan import ediliyor\n')

print('Rapor _import_raporu.txt dosyasina yazildi.')
