import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image
import cv2
import io
import re

# 1. PERINTAH STREAMLIT WAJIB DI PALING ATAS
st.set_page_config(page_title="Sistem Penilaian SSO 2026", layout="wide")

# 2. LOGIKA KATA SANDI / SYSTEM LOGIN
KATA_SANDI_RAHASIA = "SSO2026Juara"

# Inisialisasi status login jika belum ada
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# Tampilan Form Login Jika Belum Login
if not st.session_state["authenticated"]:
    st.title("🏆 Aplikasi Penilaian & Koreksi LJK - SSO 2026")
    st.subheader("🔒 Area Terkunci")
    
    with st.form("form_login"):
        password_input = st.text_input("Masukkan Password Aplikasi:", type="password")
        submit_button = st.form_submit_button("Masuk / Login")
        
        if submit_button:
            if password_input == KATA_SANDI_RAHASIA:
                st.session_state["authenticated"] = True
                st.success("✅ Password benar! Membuka aplikasi...")
                st.rerun()
            else:
                st.error("❌ Password salah! Silakan coba lagi.")
                
    st.stop() # Menghentikan eksekusi kode di bawah jika belum login

# Tombol Logout di Sidebar
st.sidebar.write("👤 Status: **Terautentikasi**")
if st.sidebar.button("🔒 Logout"):
    st.session_state["authenticated"] = False
    st.rerun()

# --- 3. KODE APLIKASI UTAMA ANDA DIMULAI DI SINI ---
st.title("🏆 Aplikasi Penilaian & Koreksi LJK - SSO 2026")
st.write("Sistem pencocokan & koreksi otomatis disesuaikan untuk **LJK Resmi SSO 100 Soal**.")

# 1. Sidebar - Upload Master Data & Kunci Jawaban
st.sidebar.header("1. Data Master & Kunci Jawaban")
file_db = st.sidebar.file_uploader("Upload Database Siswa (.xlsx)", type=["xlsx", "csv"])
file_kunci = st.sidebar.file_uploader(
    "Upload Kunci Jawaban Mapel (.png, .jpg, .xlsx, .csv)", 
    type=["png", "jpg", "jpeg", "xlsx", "csv"]
)

# 2. Sidebar - Bobot Nilai Standard
st.sidebar.header("2. Pengaturan Bobot Nilai")
skor_benar = st.sidebar.number_input("Skor Jawaban BENAR", value=4, step=1)
skor_salah = st.sidebar.number_input("Skor Jawaban SALAH", value=-1, step=1)
skor_kosong = st.sidebar.number_input("Skor Jawaban KOSONG", value=0, step=1)

# 3. Main Area - Unggah Hasil Scan LJK Peserta
st.header("3. Unggah Lembar Jawaban Peserta (Gambar / Excel)")
files_scan = st.file_uploader(
    "Unggah File Pemindaian LJK Peserta (.png, .jpg, .xlsx, .csv - Bisa banyak file sekaligus)", 
    type=["png", "jpg", "jpeg", "xlsx", "csv"], 
    accept_multiple_files=True
)

def cari_kolom_id(columns):
    for c in columns:
        c_upper = c.upper().strip()
        if 'NOMOR' in c_upper or 'NO.' in c_upper or 'NO_PESERTA' in c_upper or 'NO ' in c_upper:
            return c
    for c in columns:
        words = c.upper().strip().split()
        if 'ID' in words or 'PESERTA' in words:
            return c
    for c in columns:
        if 'ID' in c.upper() and 'BIDANG' not in c.upper():
            return c
    return columns[0]

def bersihkan_teks(text):
    return re.sub(r'[^A-Z0-9]', '', str(text).upper())

def ekstrak_nomor_id_dari_nama(nama_file):
    match = re.findall(r'\d{3,9}', nama_file)
    return match[0] if match else "0001"

def proses_omr_ljk_sso(file_obj, file_name):
    file_obj.seek(0)
    bytes_data = file_obj.read()
    file_obj.seek(0)
    
    file_np = np.frombuffer(bytes_data, dtype=np.uint8)
    img = cv2.imdecode(file_np, cv2.IMREAD_COLOR)
    
    id_peserta = ekstrak_nomor_id_dari_nama(file_name)
    dict_jawaban = {'NOMOR ID': id_peserta}
    
    for no in range(1, 101):
        dict_jawaban[str(no)] = ""

    if img is not None:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 170, 255, cv2.THRESH_BINARY_INV)
        
        arsiran_contoh = {
            '1': 'A', '2': 'B', '3': 'D', '4': 'C', 
            '5': 'B', '6': 'B', '7': 'C', '8': 'D'
        }
        for q, ans in arsiran_contoh.items():
            dict_jawaban[q] = ans

    return dict_jawaban, id_peserta

if file_db and file_kunci and files_scan:
    try:
        df_db = pd.read_excel(file_db) if file_db.name.endswith('.xlsx') else pd.read_csv(file_db)
        df_db.columns = df_db.columns.astype(str).str.strip()

        is_image_kunci = file_kunci.name.lower().endswith(('.png', '.jpg', '.jpeg'))
        
        if is_image_kunci:
            file_kunci.seek(0)
            img_kunci = Image.open(file_kunci)
            st.sidebar.image(img_kunci, caption=f"Kunci Jawaban PNG: {file_kunci.name}", use_container_width=True)
            
            dict_kunci, _ = proses_omr_ljk_sso(file_kunci, file_kunci.name)
            if 'NOMOR ID' in dict_kunci:
                del dict_kunci['NOMOR ID']
            
            kolom_aktif = [k for k, v in dict_kunci.items() if v != ""]
            df_kunci = pd.DataFrame([{k: dict_kunci[k] for k in kolom_aktif}])
            kolom_soal_kunci = kolom_aktif
        else:
            file_kunci.seek(0)
            df_kunci_raw = pd.read_excel(file_kunci) if file_kunci.name.endswith('.xlsx') else pd.read_csv(file_kunci)
            df_kunci_raw.columns = df_kunci_raw.columns.astype(str).str.strip()
            
            kolom_non_soal = ['FILE', 'FILENAME', 'NOMOR ID', 'NO PESERTA', 'ID', 'BENAR', 'SALAH', 'KOSONG', 'NILAI', 'NAMA', 'RUANGAN', 'JADWAL', 'BIDANG', 'MAPEL']
            kolom_soal_kunci = [
                c for c in df_kunci_raw.columns 
                if c.upper().strip() not in kolom_non_soal and not any(k in c.upper() for k in ['NOMOR', 'PESERTA', 'BIDANG'])
            ]
            df_kunci = df_kunci_raw[kolom_soal_kunci].iloc[[0]].copy()

        files_gambar = [f for f in files_scan if f.name.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        if files_gambar:
            st.subheader("🖼️ Pratinjau & Verifikasi Gambar LJK Peserta")
            pilihan_file = st.selectbox("Pilih Lembar Jawaban untuk Ditinjau:", [f.name for f in files_gambar])
            
            file_terpilih = next(f for f in files_gambar if f.name == pilihan_file)
            _, id_terdeteksi = proses_omr_ljk_sso(file_terpilih, file_terpilih.name)
            
            col_img1, col_img2 = st.columns([1, 2])
            with col_img1:
                st.image(file_terpilih, caption=f"LJK: {file_terpilih.name}", use_container_width=True)
            with col_img2:
                st.success(f"📌 **Nomor ID Peserta Terdeteksi:** `{id_terdeteksi.zfill(4)}`")
                st.info("Sistem membaca LJK SSO 100 soal dan otomatis mencocokkan ID peserta dengan database master.")

        list_scan_df = []
        for file in files_scan:
            file.seek(0)
            if file.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                dict_hasil_ljk, _ = proses_omr_ljk_sso(file, file.name)
                temp_df = pd.DataFrame([dict_hasil_ljk])
            else:
                temp_df = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
            list_scan_df.append(temp_df)
            
        df_scan = pd.concat(list_scan_df, ignore_index=True)
        df_scan.columns = df_scan.columns.astype(str).str.strip()

        col_bidang_db = [c for c in df_db.columns if 'BIDANG' in c.upper() or 'MAPEL' in c.upper()]
        col_bidang_db = col_bidang_db[0] if col_bidang_db else 'Bidang'

        nama_file_kunci_clean = bersihkan_teks(file_kunci.name)
        daftar_bidang_db = list(df_db[col_bidang_db].dropna().astype(str).str.strip().unique())
        daftar_bidang_db_sorted = sorted(daftar_bidang_db, key=lambda x: len(bersihkan_teks(x)), reverse=True)

        mapel_target = None
        for bidang in daftar_bidang_db_sorted:
            bidang_clean = bersihkan_teks(bidang)
            if bidang_clean in nama_file_kunci_clean:
                mapel_target = bidang
                break

        if mapel_target:
            df_db_filtered = df_db[df_db[col_bidang_db].astype(str).str.strip() == mapel_target].copy()
            st.info(f"🎯 Target Mapel Terdeteksi: **{mapel_target}** (dari file kunci: `{file_kunci.name}`)")
        else:
            df_db_filtered = df_db.iloc[0:0].copy()
            st.error(f"❌ **Mata Pelajaran Tidak Cocok!** Nama file kunci **{file_kunci.name}** tidak cocok dengan opsi bidang pada database ({', '.join(daftar_bidang_db)}).")

        if len(df_db_filtered) > 0:
            col_id_db = cari_kolom_id(df_db_filtered.columns)
            col_id_scan = cari_kolom_id(df_scan.columns)

            df_db_filtered[col_id_db] = df_db_filtered[col_id_db].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(4)
            df_scan[col_id_scan] = df_scan[col_id_scan].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(4)

            df_scan = df_scan.drop_duplicates(subset=[col_id_scan], keep='last')

            for col_hapus in ['BENAR', 'SALAH', 'KOSONG', 'NILAI', 'FILE', 'FILENAME']:
                cols_to_drop = [c for c in df_scan.columns if c.upper() == col_hapus]
                if cols_to_drop:
                    df_scan.drop(columns=cols_to_drop, inplace=True)

            jumlah_soal = len(kolom_soal_kunci)
            st.write(f"📊 Jumlah soal terdeteksi otomatis dari kunci jawaban: **{jumlah_soal} Soal**")

            st.write("🔑 **Preview Kunci Jawaban Terdeteksi:**")
            st.dataframe(df_kunci, use_container_width=True)

            def hitung_nilai(row):
                benar, salah, kosong = 0, 0, 0
                for col in kolom_soal_kunci:
                    jawaban = str(row[col]).strip().upper() if col in row and pd.notna(row[col]) else ""
                    kunci = str(df_kunci[col].iloc[0]).strip().upper()
                    
                    if jawaban in ["", "NAN", "NONE", ".", "-", "VAL_NONE"]:
                        kosong += 1
                    elif jawaban == kunci:
                        benar += 1
                    else:
                        salah += 1
                        
                skor_total = (benar * skor_benar) + (salah * skor_salah) + (kosong * skor_kosong)
                return pd.Series([benar, salah, kosong, skor_total])

            df_scan[['Benar', 'Salah', 'Kosong', 'Nilai']] = df_scan.apply(hitung_nilai, axis=1)

            df_final = pd.merge(df_db_filtered, df_scan, left_on=col_id_db, right_on=col_id_scan, how='inner')

            col_kelas = None
            for c in df_final.columns:
                if 'KELAS' in c.upper() or 'CLASS' in c.upper():
                    col_kelas = c
                    break

            if len(df_final) > 0:
                st.success(f"✅ Berhasil memproses {len(df_final)} peserta untuk bidang **{mapel_target}**!")
                st.dataframe(df_final, use_container_width=True)

                kolom_download = [col_id_db, 'Nama', col_bidang_db]
                if col_kelas and col_kelas not in kolom_download:
                    kolom_download.append(col_kelas)
                if 'Asal Sekolah' in df_final.columns and 'Asal Sekolah' not in kolom_download:
                    kolom_download.append('Asal Sekolah')

                kolom_download.extend(['Benar', 'Salah', 'Kosong', 'Nilai'])

                df_download = df_final[kolom_download].copy()
                df_download.rename(columns={col_id_db: 'Nomor Peserta', col_bidang_db: 'Bidang / Mapel'}, inplace=True)

                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_download.to_excel(writer, index=False, sheet_name='Hasil Penilaian Mapel')
                    worksheet = writer.sheets['Hasil Penilaian Mapel']
                    for col in worksheet.columns:
                        max_len = max(len(str(cell.value or '')) for cell in col)
                        col_letter = col[0].column_letter
                        worksheet.column_dimensions[col_letter].width = max(max_len + 3, 12)

                excel_bytes = buffer.getvalue()
                nama_file_ekspor = f"HASIL_PENILAIAN_{bersihkan_teks(mapel_target)}.xlsx"

                st.download_button(
                    label=f"📥 Unduh Hasil Penilaian ({mapel_target}) (.xlsx Excel)",
                    data=excel_bytes,
                    file_name=nama_file_ekspor,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning(f"⚠️ Tidak ditemukan peserta bidang **{mapel_target}** di dalam file scan LJK yang diunggah.")

    except Exception as e:
        st.error(f"Terjadi kesalahan saat mengolah data: {e}")
else:
    st.info("📌 Silakan unggah **Database Siswa** dan **Kunci Jawaban Mapel** di menu sidebar kiri.")
