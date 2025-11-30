# app.py
import streamlit as st
import pandas as pd
import json
import os
from datetime import date, datetime as dt, timedelta
import uuid

# -------------------------
# Config / Persistence
# -------------------------
DATA_FILE = "tasks.json"

def load_tasks():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_tasks(tasks):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2, default=str)

# -------------------------
# Default database jadwal kuliah (as earlier)
# -------------------------
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

# -------------------------
# Helpers: time conversions
# -------------------------
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

# -------------------------
# Duration & priority
# -------------------------
def hitung_waktu_belajar(kesulitan):
    if kesulitan == 1:
        return 30
    if kesulitan == 2:
        return 60
    if kesulitan == 3:
        return 90
    return 120

def hitung_bobot_prioritas(prioritas, kesulitan):
    return prioritas + kesulitan

# -------------------------
# Weekday -> date converter (Indonesian weekdays)
# -------------------------
WEEKDAY_MAP = {
    "Senin": 0,
    "Selasa": 1,
    "Rabu": 2,
    "Kamis": 3,
    "Jumat": 4,
    "Sabtu": 5,
    "Minggu": 6
}

def convert_weekday_to_date(weekday, week_number, month, year):
    weekday = weekday.capitalize()
    if weekday not in WEEKDAY_MAP:
        return None
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

# -------------------------
# Occupied detection & slot allocation
# -------------------------
def merge_intervals(intervals):
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: x[0])
    merged = [list(intervals[0])]
    for s,e in intervals[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s,e])
    return merged

def get_class_occupied_for_date(nim, target_date):
    occupied = []
    if not nim or nim not in DB:
        return occupied
    jadwal = DB[nim].get("jadwal_kuliah", {})
    idx_map = {0:"Senin",1:"Selasa",2:"Rabu",3:"Kamis",4:"Jumat",5:"Sabtu",6:"Minggu"}
    hari = idx_map[target_date.weekday()]
    for times in jadwal.get(hari, []):
        try:
            s,e = times.split("-")
            occupied.append([hm_to_minutes(s), hm_to_minutes(e)])
        except:
            continue
    return occupied

def get_tasks_occupied_for_date(all_tasks, target_date):
    occ = []
    for t in all_tasks:
        try:
            if parse_iso_date(t.get("date")) == target_date:
                occ.append([hm_to_minutes(t["start"]), hm_to_minutes(t["end"])])
        except:
            continue
    return occ

NIGHT_START = 19*60
NIGHT_END = 22*60
MAX_DAYS_AHEAD = 60

def find_slot_for_task(all_tasks, nim, requested_date, duration_minutes):
    search_date = requested_date
    for d_off in range(MAX_DAYS_AHEAD):
        occ = get_tasks_occupied_for_date(all_tasks, search_date) + get_class_occupied_for_date(nim, search_date)
        merged = merge_intervals(occ)
        # try place
        if not merged:
            if NIGHT_START + duration_minutes <= NIGHT_END:
                return (search_date, minutes_to_hm(NIGHT_START), minutes_to_hm(NIGHT_START + duration_minutes))
        else:
            # before first
            if NIGHT_START + duration_minutes <= merged[0][0]:
                return (search_date, minutes_to_hm(NIGHT_START), minutes_to_hm(NIGHT_START + duration_minutes))
            # between merged
            for i in range(len(merged)-1):
                gap_start = max(merged[i][1], NIGHT_START)
                gap_end = min(merged[i+1][0], NIGHT_END)
                if gap_start + duration_minutes <= gap_end:
                    return (search_date, minutes_to_hm(gap_start), minutes_to_hm(gap_start + duration_minutes))
            # after last
            last_end = max(merged[-1][1], NIGHT_START)
            if last_end + duration_minutes <= NIGHT_END:
                return (search_date, minutes_to_hm(last_end), minutes_to_hm(last_end + duration_minutes))
        search_date = search_date + timedelta(days=1)
    return None

# -------------------------
# Utility: generate id
# -------------------------
def gen_id():
    return str(uuid.uuid4())[:8]

# -------------------------
# Streamlit UI
# -------------------------
st.set_page_config(page_title="Study Scheduler", layout="wide")

# Initialize session state
if "tasks" not in st.session_state:
    st.session_state.tasks = load_tasks()
if "user_nim" not in st.session_state:
    st.session_state.user_nim = ""
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

# Sidebar menu
st.sidebar.title("Study Scheduler")
menu = st.sidebar.radio("Menu", ["Login", "Input Kegiatan", "Generate Jadwal", "Lihat Jadwal", "Edit / Hapus", "Timer", "About"])

# --- Login ---
if menu == "Login":
    st.header("Login (masukkan NIM untuk cek jadwal kuliah)")
    nim = st.text_input("NIM", value=st.session_state.user_nim)
    if st.button("Login"):
        if nim in DB:
            st.session_state.user_nim = nim
            st.session_state.user_name = DB[nim]["nama"]
            st.success(f"Login sukses. Halo, {st.session_state.user_name} ({nim})")
        else:
            st.error("NIM tidak ditemukan dalam database demo.")

# --- Input Kegiatan ---
elif menu == "Input Kegiatan":
    st.header("Input Kegiatan / Tugas")
    col1, col2 = st.columns(2)
    with col1:
        mapel = st.text_input("Mata Pelajaran / Nama Tugas")
        jenis = st.selectbox("Jenis", ["tugas", "ujian", "praktikum", "lainnya"])
        prior = st.number_input("Prioritas (1-4)", min_value=1, max_value=4, value=2)
        kes = st.number_input("Kesulitan (1-4)", min_value=1, max_value=3, value=2)
    with col2:
        date_direct = st.text_input("Tanggal langsung (YYYY-MM-DD) — kosong jika pakai minggu+hari")
        st.markdown("atau gunakan kombinasi minggu+hari:")
        hari = st.selectbox("Hari", list(WEEKDAY_MAP.keys()))
        minggu_ke = st.number_input("Minggu ke (1..5)", min_value=1, max_value=5, value=1)
        bulan = st.number_input("Bulan (1-12)", min_value=1, max_value=12, value=dt.now().month)
        tahun = st.number_input("Tahun", min_value=2023, max_value=2100, value=dt.now().year)
        nim_input = st.text_input("NIM (opsional — untuk cek jadwal kuliah)", value=st.session_state.user_nim)

    if st.button("Tambahkan ke daftar sementara"):
        # validate
        if not mapel:
            st.warning("Isi nama tugas dulu.")
        else:
            requested_date = None
            if date_direct.strip():
                dd = parse_iso_date(date_direct.strip())
                if not dd:
                    st.error("Format tanggal salah. Gunakan YYYY-MM-DD.")
                else:
                    requested_date = dd
            else:
                dd = convert_weekday_to_date(hari, minggu_ke, bulan, tahun)
                if not dd:
                    st.error("Tidak bisa konversi minggu+hari ke tanggal. Periksa input.")
                else:
                    requested_date = dd
            if requested_date:
                duration = hitung_waktu_belajar(int(kes))
                item = {
                    "id": gen_id(),
                    "mapel": mapel,
                    "jenis": jenis,
                    "requested_date": requested_date.isoformat(),
                    "prioritas": int(prior),
                    "kesulitan": int(kes),
                    "bobot": hitung_bobot_prioritas(int(prior), int(kes)),
                    "duration_minutes": duration,
                    "user_nim": nim_input.strip() or None,
                    "created_at": dt.now().isoformat()
                }
                # append to session list (temporary queue)
                if "queue" not in st.session_state:
                    st.session_state.queue = []
                st.session_state.queue.append(item)
                st.success(f"Ditambahkan ke daftar sementara: {mapel} pada {requested_date.isoformat()} ({duration} menit)")
                st.write(item)

    # show current queue
    st.subheader("Daftar sementara (belum digenerate)")
    if "queue" in st.session_state and st.session_state.queue:
        dfq = pd.DataFrame(st.session_state.queue)
        st.dataframe(dfq[["mapel","requested_date","duration_minutes","user_nim"]])
    else:
        st.write("Belum ada item sementara.")

# --- Generate Jadwal ---
elif menu == "Generate Jadwal":
    st.header("Generate Jadwal (alokasi jam malam dan simpan)")
    st.write("Ini akan memproses daftar sementara dan menyimpan yang berhasil dijadwalkan ke tasks.json")
    if "queue" not in st.session_state or not st.session_state.queue:
        st.info("Belum ada tugas di daftar sementara. Masuk ke 'Input Kegiatan' untuk menambah.")
    else:
        st.write("Daftar sementara:")
        st.dataframe(pd.DataFrame(st.session_state.queue)[["mapel","requested_date","duration_minutes","user_nim"]])
        if st.button("Jalankan Generate & Simpan"):
            tasks = load_tasks()
            queue = sorted(st.session_state.queue, key=lambda x: (-x["bobot"], x["requested_date"]))
            added = 0
            for it in queue:
                req_date = parse_iso_date(it["requested_date"])
                dur = it["duration_minutes"]
                nim_for_check = it.get("user_nim") or st.session_state.user_nim or None
                slot = find_slot_for_task(tasks, nim_for_check, req_date, dur)
                if not slot:
                    st.warning(f"Tidak menemukan slot untuk {it['mapel']} dalam batas pencarian ({MAX_DAYS_AHEAD} hari).")
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

# --- View Schedule ---
elif menu == "Lihat Jadwal":
    st.header("Lihat Jadwal")
    tasks = load_tasks()
    if not tasks:
        st.info("Belum ada tugas tersimpan.")
    else:
        df = pd.DataFrame(tasks)
        df = df.sort_values(["date","start"])
        st.subheader("Tabel tugas")
        st.dataframe(df[["mapel","date","start","end","duration_minutes","user_nim"]])

        # Plotly timeline-like view (simple)
        try:
            import plotly.express as px
            df_plot = df.copy()
            df_plot["start_dt"] = pd.to_datetime(df_plot["date"] + " " + df_plot["start"])
            df_plot["end_dt"] = pd.to_datetime(df_plot["date"] + " " + df_plot["end"])
            fig = px.timeline(df_plot, x_start="start_dt", x_end="end_dt", y="mapel", color="user_nim", title="Timeline Jadwal")
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.write("Plotly unavailable or error:", e)

# --- Edit / Hapus ---
elif menu == "Edit / Hapus":
    st.header("Edit / Hapus Tugas")
    tasks = load_tasks()
    if not tasks:
        st.info("Belum ada tugas tersimpan.")
    else:
        df = pd.DataFrame(tasks)
        df = df.sort_values(["date","start"])
        st.dataframe(df[["id","mapel","date","start","end","duration_minutes","user_nim"]])
        task_id = st.text_input("Masukkan ID tugas untuk dihapus atau diubah (lihat kolom id)")
        if st.button("Hapus tugas"):
            if not task_id:
                st.warning("Isi ID dulu.")
            else:
                tasks = [t for t in tasks if t.get("id") != task_id]
                save_tasks(tasks)
                st.success("Tugas dihapus.")
        st.markdown("---")
        st.subheader("Edit waktu tugas (re-assign)")
        edit_id = st.text_input("ID untuk re-assign (kosong jika tidak):")
        if edit_id:
            found = next((t for t in tasks if t.get("id")==edit_id), None)
            if not found:
                st.error("ID tidak ditemukan.")
            else:
                st.write("Tugas:", found.get("mapel"), found.get("date"), found.get("start"))
                # new requested date input
                with st.form("reassign_form"):
                    option = st.radio("Metode reassign", ("Tanggal langsung", "Minggu+Hari"))
                    new_date = None
                    if option == "Tanggal langsung":
                        nd = st.date_input("Pilih tanggal", value=parse_iso_date(found.get("date")))
                        new_date = nd
                    else:
                        hari = st.selectbox("Hari", list(WEEKDAY_MAP.keys()))
                        minggu_ke = st.number_input("Minggu ke", min_value=1, max_value=5, value=1)
                        bulan = st.number_input("Bulan", min_value=1, max_value=12, value=parse_iso_date(found.get("date")).month)
                        tahun = st.number_input("Tahun", min_value=2023, max_value=2100, value=parse_iso_date(found.get("date")).year)
                        new_date = convert_weekday_to_date(hari, minggu_ke, bulan, tahun)
                        if not new_date:
                            st.warning("Kombinasi minggu+hari tidak valid.")
                    submitted = st.form_submit_button("Reassign & Cari Slot Malam")
                    if submitted:
                        dur = found.get("duration_minutes", 60)
                        nim_for_check = found.get("user_nim") or st.session_state.user_nim or None
                        slot = find_slot_for_task(tasks, nim_for_check, new_date, dur)
                        if not slot:
                            st.error("Tidak menemukan slot dalam limit pencarian.")
                        else:
                            assigned_date, start, end = slot
                            # update
                            for t in tasks:
                                if t.get("id")==edit_id:
                                    t["date"] = assigned_date.isoformat()
                                    t["start"] = start
                                    t["end"] = end
                            save_tasks(tasks)
                            st.success(f"Berhasil diassign ke {assigned_date} {start}-{end}")

# --- Timer ---
elif menu == "Timer":
    st.header("Timer Belajar (web)")
    st.markdown("Ada dua mode: Countdown biasa dan Pomodoro. Alarm akan berbunyi di browser.")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Countdown biasa")
        minutes = st.number_input("Durasi (menit)", min_value=1, value=60)
        if st.button("Mulai Countdown"):
            # use JS embedded timer with audio (component)
            audio_url = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"
            html = f"""
            <div id="timer">Waktu: {minutes}:00</div>
            <audio id="alarm" src="{audio_url}"></audio>
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
            }}, 1000);
            </script>
            """
            st.components.v1.html(html, height=100)

    with col2:
        st.subheader("Pomodoro (25/5 default)")
        p_work = st.number_input("Durasi kerja (menit)", min_value=1, value=25)
        p_break = st.number_input("Durasi istirahat (menit)", min_value=1, value=5)
        if st.button("Mulai Pomodoro"):
            audio_url = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"
            html = f"""
            <div id="pom">Pomodoro: Work {p_work}m / Break {p_break}m</div>
            <audio id="alarm" src="{audio_url}"></audio>
            <script>
            var phases = [
                {{label:"Work", seconds:{p_work}*60}},
                {{label:"Break", seconds:{p_break}*60}}
            ];
            var i = 0;
            function runPhase(){{
                var phase = phases[i % phases.length];
                var seconds = phase.seconds;
                var el = document.getElementById('pom');
                var iv = setInterval(function(){{
                    if(seconds<=0){{
                        clearInterval(iv);
                        document.getElementById('alarm').play().catch(()=>{{}});
                        i++;
                        if(i<4) runPhase(); else {{
                            el.innerText = "Pomodoro selesai.";
                        }}
                        return;
                    }}
                    var m = Math.floor(seconds/60);
                    var s = seconds%60;
                    el.innerText = phase.label + " " + String(m).padStart(2,'0')+":"+String(s).padStart(2,'0');
                    seconds--;
                }}, 1000);
            }}
            runPhase();
            </script>
            """
            st.components.v1.html(html, height=120)

# --- About ---
elif menu == "About":
    st.header("Tentang Study Scheduler")
    st.markdown("""
    Aplikasi ini:
    - Menggunakan window malam default 19:00–22:00 untuk alokasi belajar.
    - Mengonversi input minggu+hari menjadi tanggal spesifik.
    - Mengecek tabrakan dengan jadwal kuliah (jika NIM diisi).
    - Menyimpan tugas ke `tasks.json`.
    - Menyediakan UI input, scheduling, tampilan, edit, dan timer.
    \n
    Tips:
    - Untuk menghindari konflik, saat menambah tugas isikan NIM (jika ada jadwal kuliah).
    - Jika alarm web tidak berbunyi, pastikan browser mengizinkan autoplay setelah interaksi (klik tombol).
    """)

# Save session tasks state to disk if changed in session (safety)
if st.session_state.tasks != load_tasks():
    save_tasks(st.session_state.tasks)
