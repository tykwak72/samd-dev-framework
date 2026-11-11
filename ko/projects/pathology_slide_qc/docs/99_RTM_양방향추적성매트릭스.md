# 🔗 양방향 추적성 매트릭스 (Requirements Traceability Matrix - RTM)

## 1. 커버리지 요약
- **총 관리 항목 수**: 34개
- **고아(Uncovered) 항목**: 0개
- **깨진 연결(Broken Links)**: 0개
- **재검토 필요(Suspect Links)**: 0개

## 2. 항목별 상·하위 양방향 연결 현황
| 항목 ID | 유형 | 버전 | 상위 연결 (Upward) | 하위 연결 (Downward) | Suspect 상태 | 사유 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| AUD-001 | AUD | v1 | SDP-001@v1 | - | ✅ 정상 | - |
| AUD-002 | AUD | v4 | SRS-001@v3<br>SRS-002@v5<br>SRS-003@v5 | - | ✅ 정상 | - |
| AUD-003 | AUD | v4 | SAD-001@v4<br>SDS-001@v4 | - | ✅ 정상 | - |
| AUD-004 | AUD | v3 | SDS-001@v4 | - | ✅ 정상 | - |
| AUD-005 | AUD | v4 | UT-001@v6<br>IT-001@v6<br>ST-001@v6<br>ST-002@v6<br>ST-003@v3<br>VT-001@v5 | REL-001@v3<br>REL-002@v4 | ✅ 정상 | - |
| AUD-006 | AUD | v3 | REL-001@v2<br>REL-002@v1 | - | ✅ 정상 | - |
| BL-001 | BL | v1 | REL-001@v2 | - | ✅ 정상 | - |
| BL-002 | BL | v1 | REL-002@v1 | - | ✅ 정상 | - |
| CR-001 | CR | v2 | PR-001@v2 | REL-002@v2 | ✅ 정상 | - |
| HAZ-SAF-001 | HAZ-SAF | v4 | SRS-001@v3 | RC-SAF-001@v4 | ✅ 정상 | - |
| HAZ-SEC-001 | HAZ-SEC | v4 | SRS-001@v3 | RC-SEC-001@v4 | ✅ 정상 | - |
| INT-001 | INT | v1 | - | LIT-001@v1<br>REG-001@v1<br>URS-001@v1 | ✅ 정상 | - |
| IT-001 | IT | v6 | SAD-001@v4 | AUD-005@v6 | ✅ 정상 | - |
| LIT-001 | LIT | v1 | INT-001@v1 | - | ✅ 정상 | - |
| PR-001 | PR | v2 | REL-001@v2 | CR-001@v2 | ✅ 정상 | - |
| RC-SAF-001 | RC-SAF | v4 | HAZ-SAF-001@v4 | SRS-002@v4<br>ST-002@v4 | ✅ 정상 | - |
| RC-SEC-001 | RC-SEC | v4 | HAZ-SEC-001@v4 | SRS-003@v4<br>UT-002@v4<br>ST-003@v4 | ✅ 정상 | - |
| REG-001 | REG | v1 | INT-001@v1 | SDP-001@v1 | ✅ 정상 | - |
| REL-001 | REL | v2 | AUD-005@v3 | AUD-006@v2<br>BL-001@v2<br>PR-001@v2 | ✅ 정상 | - |
| REL-002 | REL | v1 | AUD-005@v4<br>CR-001@v2 | AUD-006@v1<br>BL-002@v1 | ✅ 정상 | - |
| SAD-001 | SAD | v4 | SRS-001@v3<br>SRS-002@v5<br>SRS-003@v5 | IT-001@v4<br>AUD-003@v4 | ✅ 정상 | - |
| SDP-001 | SDP | v1 | REG-001@v1 | AUD-001@v1 | ✅ 정상 | - |
| SDS-001 | SDS | v4 | SRS-001@v3<br>SRS-002@v5<br>SRS-003@v5 | UT-001@v4<br>AUD-003@v4<br>AUD-004@v4 | ✅ 정상 | - |
| SOUP-001 | SOUP | v3 | SRS-001@v3 | - | ✅ 정상 | - |
| SRS-001 | SRS | v3 | URS-001@v2 | SAD-001@v3<br>SOUP-001@v3<br>SDS-001@v3<br>ST-001@v3<br>HAZ-SAF-001@v3<br>HAZ-SEC-001@v3<br>AUD-002@v3 | ✅ 정상 | - |
| SRS-002 | SRS | v5 | URS-001@v2<br>RC-SAF-001@v4 | SAD-001@v5<br>SDS-001@v5<br>ST-002@v5<br>AUD-002@v5 | ✅ 정상 | - |
| SRS-003 | SRS | v5 | URS-001@v2<br>RC-SEC-001@v4 | SAD-001@v5<br>SDS-001@v5<br>ST-003@v5<br>AUD-002@v5 | ✅ 정상 | - |
| ST-001 | ST | v6 | SRS-001@v3 | AUD-005@v6 | ✅ 정상 | - |
| ST-002 | ST | v6 | SRS-002@v5<br>RC-SAF-001@v4 | AUD-005@v6 | ✅ 정상 | - |
| ST-003 | ST | v3 | SRS-003@v5<br>RC-SEC-001@v4 | AUD-005@v3 | ✅ 정상 | - |
| URS-001 | URS | v2 | INT-001@v1 | SRS-001@v2<br>SRS-002@v2<br>SRS-003@v2<br>VT-001@v2 | ✅ 정상 | - |
| UT-001 | UT | v6 | SDS-001@v4 | AUD-005@v6 | ✅ 정상 | - |
| UT-002 | UT | v6 | RC-SEC-001@v4 | - | ✅ 정상 | - |
| VT-001 | VT | v5 | URS-001@v2 | AUD-005@v5 | ✅ 정상 | - |