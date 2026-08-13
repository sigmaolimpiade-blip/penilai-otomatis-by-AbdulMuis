import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image
import cv2
import io
import re

# 1. PERINTAH STREAMLIT WAJIB DI PALING ATAS
st.set_page_config(page_title="Sistem Penilaian SSO 2026", layout="wide")

# ==============================================================================
# 🔒 SISTEM LOGIN & OTENTIKASI
# ==============================================================================
KATA_SANDI_RAHASIA = "SSO2026Juara"

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🏆 Aplikasi Penilaian & Koreksi LJK - SSO 2026")
    st.subheader("🔒 Area Terkunci - Silakan Login")
    
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
                
    st.stop()

st.sidebar.write("👤 Status: **Terautentikasi**")
if st.sidebar.button("🔒 Logout"):
    st.session_state["authenticated"] = False
    st.rerun()

# ==============================================================================
# 🚀 APLIKASI UTAMA
# ==============================================================================

st.title("🏆 Aplikasi Penilaian & Koreksi LJK - SSO 2026")
st.write("Sistem pencocokan & koreksi otomatis disesuaikan untuk **LJK Resmi SSO 100 Soal**.")

# 1. Sidebar - Upload Master Data & Kunci Jawaban
st.sidebar.header("1. Data Master & Kunci Jawaban")
file_db = st.sidebar.file_uploader("Upload Database Siswa (.xlsx, .csv)", type=["xlsx", "csv"])
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

def urutkan_4_titik_sudut(pts):
    # Mengurutkan titik: Top-Left, Top-Right, Bottom-Right, Bottom-Left
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]       # Top-Left (x+y terkecil)
    rect[2] = pts[np.argmax(s)]       # Bottom-Right (x+y terbesar)
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]    # Top-Right (x-y terkecil)
    rect[3] = pts[np.argmax(diff)]    # Bottom-Left (x-y terbesar)
    return rect

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

    if img is None:
        return dict_jawaban, id_peserta

    # 1. Grayscale & Thresholding
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )

    # 2. Deteksi Kontur Kotak Sudut (Alignment Marks)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    box_corners = []

    for c in contours:
        x, y, w_box, h_box = cv2.boundingRect(c)
        aspect_ratio = float(w_box) / h_box
        area = cv2.contourArea(c)
        
        if 0.7 <= aspect_ratio <= 1.3 and area > (img.shape[0] * img.shape[1] * 0.001):
            box_corners.append([x + w_box // 2, y + h_box // 2])

    # Transformasi Perspektif jika ditemukan 4 sudut atau lebih
    if len(box_corners) >= 4:
        pts1 = urutkan_4_titik_sudut(np.array(box_corners[:4], dtype="float32"))
        target_w, target_h = 1000, 1400
        pts2 = np.float32([[0, 0], [target_w, 0], [target_w, target_h], [0, target_h]])
        
        M = cv2.getPerspectiveTransform(pts1, pts2)
        warped_thresh = cv2.warpPerspective(thresh, M, (target_w, target_h))
    else:
        warped_thresh = cv2.resize(thresh, (1000, 1400))

    # 3. Pembacaan Jawaban (4 Kolom x 25 Soal)
    kolom_x_center = [
        [182, 218, 254, 290],  # Kolom 1 (1-25)
        [412, 448, 484, 520],  # Kolom 2 (26-50)
        [642, 678, 714, 750],  # Kolom 3 (51-75)
        [872, 908, 944, 980]   # Kolom 4 (76-100)
    ]
    
    y_start_base = 550
    y_step = 27
    opsi_labels = ['A', 'B', 'C', 'D']

    for col_idx in range(4):
        for row_idx in range(25):
            no_soal = str(col_idx * 25 + row_idx + 1)
            y_center = y_start_base + (row_idx * y_step)
            
            density_list = []
            for opt_idx in range(4):
                x_center = kolom_x_center[col_idx][opt_idx]
                roi = warped_thresh[max(0, y_center-8):min(1400, y_center+8), 
                                    max(0, x_center-8):min(1000, x_center+8)]
                count = cv2.countNonZero(roi)
                density_list.append(count)
            
            max_density = max(density_list)
            max_idx = density_list.index(max_density)
            avg_other = (sum(density_list) - max_density) / 3.0
            
            if max_density > 80 and max_density > (avg_other * 1.8):
                dict_jawaban[no_soal] = opsi_labels[max_idx]

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

            # Cari Nama Kolom Dinamis untuk Ekspor
            col_nama = next((c for c in df_final.columns if 'NAMA' in c.upper()), None)
            col_kelas = next((c for c in df_final.columns if 'KELAS' in c.upper() or 'CLASS' in c.upper()), None)

            if len(df_final) > 0:
                st.success(f"✅ Berhasil memproses {len(df_final)} peserta untuk bidang **{mapel_target}**!")
                st.dataframe(df_final, use_container_width=True)

                kolom_download = [col_id_db]
                if col_nama:
                    kolom_download.append(col_nama)
                kolom_download.append(col_bidang_db)
                
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
