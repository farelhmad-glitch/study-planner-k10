# app.py - Study Scheduler (Full Version B) - Streamlit
# Requirements: streamlit, pandas, plotly
# Run: streamlit run app.py

import streamlit as st
import pandas as pd
import json, os, uuid
from datetime import date, datetime as dt, timedelta
import math

# ----------------------------
# Config / Persistence
# ----------------------------
DATA_FILE = "tasks.json"
DEFAULT_NIGHT_START = 19 * 60  # 19:00 in minutes
DEFAULT_NIGHT_END = 22 * 60    # 22:00
MAX_DAYS_AHEAD = 60

def load_tasks():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_tasks(tasks):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2, default=str)

# ----------------------------
# Database mahasiswa (example)
# ----------------------------
def buat_database_mahasiswa():
    database = {
        "16725186": {
            "nama": "Jean Fide Tjahjamuljo",
            "jadwal_kuliah": {
                "Senin": ["08:00-10:00", "13:00-15:00"],
                "Selasa": ["10:00-12:00"],
                "Rabu": ["08:00-10:00", "15:00-17:00"],
                "Kamis": ["13:00-15:00"],
                "Jumat": ["10:00-12:00"]
            }
        },
        "16725193": {
            "nama": "Farel Ahmad",
            "jadwal_kuliah": {
                "Senin": ["10:00-12:00"],
                "Selasa": ["08:00-10:00", "13:00-15:00"],
                "Rabu": ["10:00-12:00"],
                "Kamis": ["08:00-10:00", "15:00-17:00"],
                "Jumat": ["13:00-15:00"]
            }
        },
        "16725305": {
            "nama": "Nindya Cettakirana Bintoro",
            "jadwal_kuliah": {
                "Senin": ["08:00-10:00"],
                "Selasa": ["10:00-12:00", "15:00-17:00"],
                "Rabu": ["13:00-15:00"],
                "Kamis": ["08:00-10:00", "13:00-15:00"],
                "Jumat": ["10:00-12:00"]
            }
        }
    }
    return database

DB = buat_database_mahasiswa()

# ----------------------------
# Helpers: time conversions
# ----------------------------
def hm_to_minutes(hm):
    h, m = map(int, hm.split(":"))
    return h*60 + m

def minutes_to_hm(minutes):
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"

def parse_iso_date(s):
    try:
        return dt.strptime(s, "%Y-%m-%d").date()
    except:
        return None

# ----------------------------
# Priority & duration mapping
# ----------------------------
def hitung_waktu_belajar(kesulitan):
    # kesulitan 1..4
    if kesulitan == 1: return 30
    if kesulitan == 2: return 60
    if kesulitan == 3: return 90
    return 120

def hitung_bobot_prioritas(prioritas, kesulitan):
    return prioritas + kesulitan

# ----------------------------
# Weekday -> date converter (Indonesian weekdays)
# ----------------------------
WEEKDAY_MAP = {"Senin":0,"Selasa":1,"Rabu":2,"Kamis":3,"Jumat":4,"Sabtu":5,"Minggu":6}
IDX_TO_DAY = {v:k for k,v in WEEKDAY_MAP.items()}

def convert_weekday_to_date(weekday, week_number, month, year):
    weekday = weekday.capitalize()
    if weekday not in WEEKDAY_MAP: return None
    target = WEEKDAY_MAP[weekday]
    try:
        d = date(year, month, 1)
    except:
        return None
    count = 0
    while d.month == month:
        if d.weekday() == target:
            count += 1
            if count == week_number:
                return d
        d += timedelta(days=1)
    return None

# ----------------------------
# Merge intervals helper
# ----------------------------
def merge_intervals(intervals):
    if not intervals: return []
    intervals = sorted(intervals, key=lambda x: x[0])
    merged = [list(intervals[0])]
    for s,e in intervals[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s,e])
    return merged

def get_class_occupied_for_date(nim, target_date):
    occ = []
    if not nim or nim not in DB: return occ
    jadwal = DB[nim].get("jadwal_kuliah", {})
    hari = IDX_TO_DAY[target_date.weekday()]
    for times in jadwal.get(hari, []):
        try:
            s,e = times.split("-")
            occ.append([hm_to_minutes(s), hm_to_minutes(e)])
        except:
            continue
    return occ

def get_tasks_occupied_for_date(all_tasks, target_date, ignore_task_id=None):
    occ = []
    for t in all_tasks:
        if ignore_task_id and t.get("id") == ignore_task_id: 
            continue
        try:
            if parse_iso_date(t.get("date")) == target_date:
                occ.append([hm_to_minutes(t["start"]), hm_to_minutes(t["end"])])
        except:
            continue
    return occ

# ----------------------------
# Slot finder (consider tasks + class schedule)
# ----------------------------
def find_slot_for_task(all_tasks, nim, requested_date, duration_minutes, ignore_task_id=None,
                       night_start=DEFAULT_NIGHT_START, night_end=DEFAULT_NIGHT_END, max_days=MAX_DAYS_AHEAD):
    search_date = requested_date
    for offset in range(max_days):
        occ = get_tasks_occupied_for_date(all_tasks, search_date, ignore_task_id=ignore_task_id) + get_class_occupied_for_date(nim, search_date)
        merged = merge_intervals(occ)
        if not merged:
            if night_start + duration_minutes <= night_end:
                return (search_date, minutes_to_hm(night_start), minutes_to_hm(night_start + duration_minutes))
        else:
            # before first
            if night_start + duration_minutes <= merged[0][0]:
                return (search_date, minutes_to_hm(night_start), minutes_to_hm(night_start + duration_minutes))
            # between intervals
            for i in range(len(merged)-1):
                gap_start = max(merged[i][1], night_start)
                gap_end = min(merged[i+1][0], night_end)
                if gap_start + duration_minutes <= gap_end:
                    return (search_date, minutes_to_hm(gap_start), minutes_to_hm(gap_start + duration_minutes))
            # after last
            last_end = max(merged[-1][1], night_start)
            if last_end + duration_minutes <= night_end:
                return (search_date, minutes_to_hm(last_end), minutes_to_hm(last_end + duration_minutes))
        search_date = search_date + timedelta(days=1)
    return None

# ----------------------------
# ID gen helper
# ----------------------------
def gen_id():
    return str(uuid.uuid4())[:8]

# ----------------------------
# UI Start - Streamlit
# ----------------------------
st.set_page_config(page_title="Study Scheduler (Full)", layout="wide")
st.title("Study Scheduler — Versi Lengkap (Streamlit)")

# initialize session state
if "queue" not in st.session_state: st.session_state.queue = []
if "tasks" not in st.session_state: st.session_state.tasks = load_tasks()
if "user_nim" not in st.session_state: st.session_state.user_nim = ""
if "user_name" not in st.session_state: st.session_state.user_name = ""

# Sidebar navigation
st.sidebar.title("Menu")
menu = st.sidebar.radio("", ["Login", "Input Kegiatan", "Generate Jadwal", "Lihat Jadwal", "Edit / Hapus", "Timer", "Export", "About"])

# --- Login Page ---
if menu == "Login":
    st.header("Login NIM (untuk cek jadwal kuliah otomatis)")
    nim = st.text_input("Masukkan NIM demo (contoh: 16725193):", st.session_state.user_nim)
    if st.button("Login"):
        if nim in DB:
            st.session_state.user_nim = nim
            st.session_state.user_name = DB[nim]["nama"]
            st.success(f"Login berhasil. Halo, {st.session_state.user_name} ({nim})")
        else:
            st.error("NIM tidak ditemukan di database demo.")
    if st.session_state.user_nim:
        st.info(f"Akun saat ini: {st.session_state.user_name} ({st.session_state.user_nim})")

# --- Input Kegiatan ---
elif menu == "Input Kegiatan":
    st.header("Input Kegiatan / Tugas (Lengkap)")
    col1, col2 = st.columns([2,1])
    with col1:
        mapel = st.text_input("Nama tugas / mata pelajaran")
        jenis = st.selectbox("Jenis", ["tugas","ujian","praktikum","lainnya"])
        prior = st.slider("Prioritas (1=rendah .. 4=tinggi)", 1, 4, 2)
        kes = st.slider("Kesulitan (1..4) — berpengaruh pada durasi", 1, 4, 2)
        deadline = st.text_input("Deadline (YYYY-MM-DD) - opsional (kosong jika tidak ada)")
    with col2:
        st.markdown("**Atau pilih minggu + hari**")
        hari = st.selectbox("Hari (untuk konversi minggu→tanggal)", list(WEEKDAY_MAP.keys()))
        minggu_ke = st.number_input("Minggu ke", min_value=1, max_value=5, value=1)
        bulan = st.number_input("Bulan (1-12)", min_value=1, max_value=12, value=dt.now().month)
        tahun = st.number_input("Tahun", min_value=2023, max_value=2100, value=dt.now().year)
        nim_input = st.text_input("Masukkan NIM (opsional, agar jadwal kuliah dicek)", value=st.session_state.user_nim)
    if st.button("Tambahkan ke daftar sementara (queue)"):
        if not mapel:
            st.warning("Isi nama tugas dulu.")
        else:
            # determine requested_date
            requested_date = None
            if deadline.strip():
                parsed = parse_iso_date(deadline.strip())
                if not parsed:
                    st.error("Format deadline salah (YYYY-MM-DD).")
                else:
                    requested_date = parsed
            else:
                conv = convert_weekday_to_date(hari, minggu_ke, bulan, tahun)
                if not conv:
                    st.error("Gagal konversi minggu+hari menjadi tanggal (cek input).")
                else:
                    requested_date = conv
            if requested_date:
                dur = hitung_waktu_belajar(kes)
                item = {
                    "id": gen_id(),
                    "mapel": mapel,
                    "jenis": jenis,
                    "requested_date": requested_date.isoformat(),
                    "deadline": deadline.strip(),
                    "prioritas": int(prior),
                    "kesulitan": int(kes),
                    "bobot": hitung_bobot_prioritas(int(prior), int(kes)),
                    "duration_minutes": dur,
                    "user_nim": nim_input.strip() or None,
                    "created_at": dt.now().isoformat()
                }
                st.session_state.queue.append(item)
                st.success(f"Ditambahkan ke queue: {mapel} pada {requested_date.isoformat()} ({dur} menit)")
    st.subheader("Daftar sementara (queue)")
    if st.session_state.queue:
        dfq = pd.DataFrame(st.session_state.queue)
        st.dataframe(dfq[["mapel","requested_date","duration_minutes","user_nim","bobot"]])
        if st.button("Kosongkan queue"):
            st.session_state.queue = []
            st.info("Queue dikosongkan.")
    else:
        st.write("Belum ada item di queue.")

# --- Generate Jadwal ---
elif menu == "Generate Jadwal":
    st.header("Generate Jadwal & Simpan (menggunakan bobot & deadline)")
    st.write("Proses akan mengurutkan queue berdasarkan bobot (prioritas+kesulitan) turun, lalu deadline (terdekat).")
    if not st.session_state.queue:
        st.info("Queue kosong. Tambah tugas di menu 'Input Kegiatan'.")
    else:
        dfq = pd.DataFrame(st.session_state.queue)
        st.subheader("Queue saat ini")
        st.dataframe(dfq[["mapel","requested_date","duration_minutes","user_nim","bobot","deadline"]])
        max_days = st.number_input("Maks hari pencarian slot ke depan jika perlu (hari)", min_value=7, max_value=365, value=MAX_DAYS_AHEAD)
        night_start_h = st.number_input("Jam mulai malam (jam, 24h)", min_value=0, max_value=23, value=19)
        night_end_h = st.number_input("Jam akhir malam (jam, 24h)", min_value=1, max_value=23, value=22)
        if st.button("Jalankan Generate & Simpan"):
            tasks = load_tasks()
            # sort queue with bobot desc, deadline asc (deadline earliest first, empty last)
            def deadline_key(it):
                if it.get("deadline"):
                    d = parse_iso_date(it["deadline"])
                    return d or dt.max.date()
                return dt.max.date()
            queue_sorted = sorted(st.session_state.queue, key=lambda x: (-x["bobot"], deadline_key(x)))
            added = 0
            for it in queue_sorted:
                req = parse_iso_date(it["requested_date"])
                dur = it["duration_minutes"]
                nim_for_check = it.get("user_nim") or st.session_state.user_nim or None
                slot = find_slot_for_task(tasks, nim_for_check, req, dur, ignore_task_id=None,
                                          night_start=night_start_h*60, night_end=night_end_h*60, max_days=max_days)
                if not slot:
                    st.warning(f"Gagal alokasikan slot untuk {it['mapel']} (tidak ada slot dalam {max_days} hari).")
                    continue
                assigned_date, start, end = slot
                newtask = {
                    "id": it["id"],
                    "mapel": it["mapel"],
                    "jenis": it["jenis"],
                    "date": assigned_date.isoformat(),
                    "start": start,
                    "end": end,
                    "duration_minutes": dur,
                    "user_nim": nim_for_check,
                    "created_at": dt.now().isoformat()
                }
                tasks.append(newtask)
                added += 1
                st.success(f"Terjadwal: {newtask['mapel']} pada {newtask['date']} {newtask['start']}-{newtask['end']}")
            save_tasks(tasks)
            st.session_state.queue = []
            st.info(f"Selesai. {added} tugas tersimpan ke {DATA_FILE}.")

# --- Lihat Jadwal ---
elif menu == "Lihat Jadwal":
    st.header("Lihat Jadwal Tersimpan")
    tasks = load_tasks()
    if not tasks:
        st.info("Belum ada tugas tersimpan.")
    else:
        df = pd.DataFrame(tasks)
        df = df.sort_values(["date","start"])
        st.subheader("Tabel Tugas")
        st.dataframe(df[["id","mapel","date","start","end","duration_minutes","user_nim"]])

        # timeline via plotly
        try:
            import plotly.express as px
            df_plot = df.copy()
            df_plot["start_dt"] = pd.to_datetime(df_plot["date"] + " " + df_plot["start"])
            df_plot["end_dt"] = pd.to_datetime(df_plot["date"] + " " + df_plot["end"])
            fig = px.timeline(df_plot, x_start="start_dt", x_end="end_dt", y="mapel", color="user_nim", title="Timeline Jadwal")
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.write("Plotly error/atau belum terinstal:", e)

# --- Edit / Hapus ---
elif menu == "Edit / Hapus":
    st.header("Edit / Hapus Tugas")
    tasks = load_tasks()
    if not tasks:
        st.info("Belum ada tugas tersimpan.")
    else:
        df = pd.DataFrame(tasks).sort_values(["date","start"])
        st.dataframe(df[["id","mapel","date","start","end","duration_minutes","user_nim"]])
        st.markdown("### Hapus tugas")
        del_id = st.text_input("Masukkan ID tugas untuk dihapus")
        if st.button("Hapus tugas"):
            if not del_id:
                st.warning("Isi ID terlebih dahulu.")
            else:
                new_tasks = [t for t in tasks if t.get("id") != del_id]
                save_tasks(new_tasks)
                st.success("Tugas dihapus.")
        st.markdown("---")
        st.markdown("### Reassign / Edit Waktu Tugas (FIXED: hapus sementara sebelum cari slot)")
        edit_id = st.text_input("Masukkan ID tugas untuk reassign")
        if edit_id:
            found = next((t for t in tasks if t.get("id")==edit_id), None)
            if not found:
                st.error("ID tidak ditemukan.")
            else:
                st.write("Tugas:", found["mapel"], found["date"], found["start"])
                with st.form("reassign_form"):
                    method = st.radio("Metode input tanggal baru", ["Tanggal langsung", "Minggu + Hari"])
                    new_date = None
                    if method == "Tanggal langsung":
                        nd = st.date_input("Pilih tanggal", value=parse_iso_date(found["date"]))
                        new_date = nd
                    else:
                        hari2 = st.selectbox("Hari", list(WEEKDAY_MAP.keys()))
                        minggu2 = st.number_input("Minggu ke", 1, 5, 1)
                        bulan2 = st.number_input("Bulan", 1, 12, parse_iso_date(found["date"]).month)
                        tahun2 = st.number_input("Tahun", 2023, 2100, parse_iso_date(found["date"]).year)
                        new_date = convert_weekday_to_date(hari2, minggu2, bulan2, tahun2)
                        if not new_date:
                            st.warning("Kombinasi minggu+hari tidak valid.")
                    submitted = st.form_submit_button("Cari Slot & Simpan")
                    if submitted:
                        if not new_date:
                            st.error("Tanggal baru invalid.")
                        else:
                            # remove old task temporarily
                            tasks_without_old = [t for t in tasks if t.get("id") != edit_id]
                            dur = found.get("duration_minutes", 60)
                            nim_for_check = found.get("user_nim") or st.session_state.user_nim or None
                            slot = find_slot_for_task(tasks_without_old, nim_for_check, new_date, dur, ignore_task_id=None)
                            if not slot:
                                st.error("Tidak menemukan slot malam yang cocok dalam batas pencarian.")
                            else:
                                assigned_date, start, end = slot
                                # update found
                                found["date"] = assigned_date.isoformat()
                                found["start"] = start
                                found["end"] = end
                                # rebuild list + save (preserve others)
                                updated = tasks_without_old + [found]
                                save_tasks(updated)
                                st.success(f"Berhasil reassign: {found['mapel']} → {found['date']} {found['start']}-{found['end']}")

# --- Timer ---
elif menu == "Timer":
    st.header("Timer Belajar")
    st.write("Timer client-side (browser) dengan bunyi alarm. Gunakan tombol untuk mulai agar browser mengizinkan audio.")
    col1,col2 = st.columns(2)
    with col1:
        st.subheader("Countdown Biasa")
        minutes = st.number_input("Durasi (menit)", min_value=1, value=60)
        if st.button("Mulai Countdown"):
            audio = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"
            html = f"""
            <div id="timer">Waktu: {minutes}:00</div>
            <audio id="alarm" src="{audio}"></audio>
            <script>
            var seconds = {minutes}*60;
            var el = document.getElementById('timer');
            var iv = setInterval(function(){{
                if(seconds<=0){{
                    clearInterval(iv);
                    el.innerText = "Waktu Habis!";
                    document.getElementById('alarm').play().catch(()=>{{}});
                    return;
                }}
                var m = Math.floor(seconds/60);
                var s = seconds%60;
                el.innerText = "Waktu: "+String(m).padStart(2,'0')+":"+String(s).padStart(2,'0');
                seconds--;
            }},1000);
            </script>
            """
            st.components.v1.html(html, height=120)
    with col2:
        st.subheader("Pomodoro")
        work = st.number_input("Durasi kerja (menit)", min_value=1, value=25)
        brk = st.number_input("Durasi istirahat (menit)", min_value=1, value=5)
        rounds = st.number_input("Jumlah siklus", min_value=1, max_value=8, value=4)
        if st.button("Mulai Pomodoro"):
            audio = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"
            html = f"""
            <div id="pom">Pomodoro</div>
            <audio id="alarm" src="{audio}"></audio>
            <script>
            var phases = [];
            for(var i=0;i<{rounds};i++) phases.push({{label:"Work", seconds:{work}*60}}, {{label:"Break", seconds:{brk}*60}});
            var idx=0;
            function runPhase(){{
                if(idx>=phases.length){{ document.getElementById('pom').innerText='Pomodoro selesai.'; return; }}
                var phase = phases[idx];
                var seconds = phase.seconds;
                var el = document.getElementById('pom');
                var iv = setInterval(function(){{
                    if(seconds<=0){{
                        clearInterval(iv);
                        document.getElementById('alarm').play().catch(()=>{{}});
                        idx++;
                        runPhase();
                        return;
                    }}
                    var m = Math.floor(seconds/60);
                    var s = seconds%60;
                    el.innerText = phase.label + ' ' + String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
                    seconds--;
                }},1000);
            }}
            runPhase();
            </script>
            """
            st.components.v1.html(html, height=160)

# --- Export ---
elif menu == "Export":
    st.header("Export / Backup")
    tasks = load_tasks()
    if not tasks:
        st.info("Belum ada data untuk di-export.")
    else:
        df = pd.DataFrame(tasks).sort_values(["date","start"])
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", csv, file_name="tasks_export.csv", mime="text/csv")
        st.download_button("Download JSON", json.dumps(tasks, ensure_ascii=False, indent=2), file_name="tasks_export.json", mime="application/json")

# --- About ---
elif menu == "About":
    st.header("Tentang Aplikasi")
    st.markdown("""
    **Study Scheduler (Versi Lengkap)**\n
    - Alokasi jam malam default 19:00–22:00 (konfigurasi saat generate).
    - Mengonversi minggu+hari → tanggal.
    - Menggunakan prioritas & kesulitan untuk menentukan urutan scheduling.
    - Mengecek tabrakan dengan jadwal kuliah (jika NIM diisi).
    - Menyimpan ke `tasks.json`.
    - Menyediakan fitur edit/reassign yang sudah diperbaiki (hapus sementara sebelum mencari slot).
    \n
    Jika ada penyesuaian (mis. ubah window malam, export ke Google Calendar, integrasi notifikasi), bilang saja.
    """)

# Always sync session tasks to disk if session changes that differ
if st.session_state.tasks != load_tasks():
    save_tasks(st.session_state.tasks)

