"""Config tim DATA uji (tim sumber) untuk pembangun fixture: dipakai bangun_fixture.py dan bangun_misi1.py.
Path `sumber` relatif; tests/generator/bantu_tim.py menggantinya dengan path dunia uji."""

R1 = "(?:^|[\\s'\";(])/(?:ip |interface|routing|system)|\\bR1\\b|(?i:mikrotik|routeros)"


def tim_fixture(agen):
    return {
        "_catatan": "DATA uji: config tim sumber (bukan config pemasangan). Path sumber relatif; bantu_tim.tulis_tim() menggantinya dengan path dunia uji.",
        "versi": 1,
        "orang": [
            {"id": "akbar", "nama": "Pak Akbar", "peran": "Pemilik tim", "induk": []},
            {"id": "dicky", "nama": "Mas Dicky", "peran": "Pemberi order", "induk": ["akbar"]},
            {"id": "jati", "nama": "Mas Jati", "peran": "Pemberi order", "induk": ["akbar"]}],
        "penonton": ["akbar", "dicky", "jati"],
        "pemilik": "akbar",
        "koordinator": "ajeng",
        "cto": "desy",
        "agen": agen,
        "sumber": {"activity": "activity.jsonl", "profil": "profiles", "workspace": "workspace",
                   "workspace_kontainer": "/workspace", "brief": "workspace/brief", "lock": "workspace/locks",
                   "handoff": None, "proc": "proc"},
        "pola": {"brief_nama": "[0-9]{4}-[0-9]{2}-[0-9]{2}-{pelaksana}-(?P<sisa>.+)\\.md",
                 "lock_nama": "[a-z0-9]+(?:-[a-z0-9]+)*", "lock_pemisah_subtugas": None,
                 "peminta": "\\W*Peminta\\b"},
        "kategori_perintah": [
            {"pola": "(?s)\\bssh\\b.*\\bbskdev-host\\b", "teks": "menjalankan perintah di bskdev"},
            {"pola": R1, "teks": "mengakses R1", "sesudah_panggil": True}],
        "tool": {"awalan_bank_dokumen": "mcp__obsidian_bsk__", "catat_progres": "mcp__obsidian_bsk__catat_progres",
                 "setor": "mcp__obsidian_bsk__setor"},
    }


AGEN_SUMBER = {
    "ajeng": {"nama": "Ajeng", "peran": "Koordinator", "induk": ["dicky", "jati"], "ruang": "koordinasi"},
    "desy": {"nama": "Desy", "peran": "CTO", "induk": ["ajeng"], "ruang": "teknik"},
    "via": {"nama": "Via", "peran": "Riset dan peraturan", "induk": ["ajeng"], "ruang": "riset"},
    "uci": {"nama": "Uci", "peran": "QA/QC", "induk": ["ajeng"], "ruang": "qa"},
    "alfa": {"nama": "Alfa", "peran": "Tech Lead", "induk": ["desy"], "ruang": "teknik"},
    "beta": {"nama": "Beta", "peran": "Tech Lead", "induk": ["desy"], "ruang": "teknik"},
    "carli": {"nama": "Carli", "peran": "Tech Lead", "induk": ["desy"], "ruang": "teknik"},
    "delta": {"nama": "Delta", "peran": "Tech Lead", "induk": ["desy"], "ruang": "teknik"},
    "echo": {"nama": "Echo", "peran": "Tech Lead", "induk": ["desy"], "ruang": "teknik"},
}
