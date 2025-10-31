export default function WeeklyMeals() {
  const [rows, setRows] = React.useState(props.rows || []);

  const onChange = (i, key, val) => {
    setRows((prev) => {
      const next = [...prev];
      next[i] = { ...next[i], [key]: val };
      return next;
    });
  };

  return (
    <div className="w-full max-w-3xl mx-auto">
      {/* 입력창을 확실히 보이게 만드는 전용 스타일 */}
      <style>{`
        .dark-table { background:#000; color:#fff; }
        .dark-table thead tr { background:#1f2937; }           /* 회색 헤더 */
        .dark-table tbody tr { border-top:1px solid #374151; }  /* 줄 구분선 */
        .dark-input {
          width:100%;
          background:#000;       /* 입력창 배경 검정 */
          color:#fff;            /* 입력 글자 흰색 */
          border:1px solid #4b5563;
          border-radius:0.375rem; /* rounded */
          padding:0.25rem;       /* p-1 */
          outline:none;
        }
        .dark-input::placeholder {
          color:#9ca3af;         /* placeholder 회색 */
        }
        .dark-input:focus {
          border-color:#60a5fa;  /* 파란 포커스 테두리 */
          box-shadow:0 0 0 2px rgba(96,165,250,0.4);
        }
        .btn {
          padding:0.25rem 0.75rem;
          border-radius:0.375rem;
          transition:background 120ms ease;
        }
        .btn-cancel {
          border:1px solid #9ca3af; color:#fff; background:transparent;
        }
        .btn-cancel:hover { background:#374151; }
        .btn-submit {
          background:#fff; color:#000; border:1px solid transparent;
        }
        .btn-submit:hover { background:#f3f4f6; }
        th, td { padding:0.5rem; text-align:left; }
      `}</style>

      <div className="overflow-auto border rounded-xl shadow-lg dark-table">
        <table className="min-w-full text-sm">
          <thead>
            <tr>
              <th>무슨 요일에?</th>
              <th>뭐 먹었어?</th>
              <th>어디서?</th>
              <th>언제?</th>
              <th>얼마 썼어?</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.dayKey}>
                <td>{r.dayLabel}</td>
                <td>
                  <input
                    className="dark-input"
                    value={r.what}
                    onChange={(e) => onChange(i, "what", e.target.value)}
                    placeholder="예) 비빔밥"
                    autoComplete="off"
                  />
                </td>
                <td>
                  <input
                    className="dark-input"
                    value={r.where}
                    onChange={(e) => onChange(i, "where", e.target.value)}
                    placeholder="예) 성수 OO식당"
                    autoComplete="off"
                  />
                </td>
                <td>
                  <input
                    className="dark-input"
                    value={r.time}
                    onChange={(e) => onChange(i, "time", e.target.value)}
                    placeholder="예) 12:30"
                    autoComplete="off"
                  />
                </td>
                <td>
                  <input
                    className="dark-input"
                    value={r.note}
                    onChange={(e) => onChange(i, "note", e.target.value)}
                    placeholder="예) 8,000원"
                    autoComplete="off"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 버튼 영역 */}
      <div className="flex gap-2 justify-end mt-3">
        <button className="btn btn-cancel" onClick={() => cancelElement()}>
          취소
        </button>
        <button
          className="btn btn-submit"
          onClick={() => submitElement({ submitted: true, rows })}
        >
          제출
        </button>
      </div>
    </div>
  );
}
