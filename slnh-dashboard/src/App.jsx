import { useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, ReferenceLine, AreaChart, Area
} from 'recharts'

const C = {
  green:  '#22c55e', red:    '#ef4444', yellow: '#f59e0b',
  blue:   '#3b82f6', indigo: '#6366f1', gray:   '#6b7280',
  darkBg: '#0f172a', cardBg: '#1e293b', border: '#334155',
  text:   '#f1f5f9', muted:  '#94a3b8', cyan:   '#06b6d4',
  orange: '#f97316', purple: '#a855f7',
}

// ── 데이터 ───────────────────────────────────────────────
const mwData = [
  { name: 'Briscoe 풍력', mw: 150, type: '운영(발전)', color: C.green },
  { name: 'Kati 1A',      mw: 48,  type: '운영(컴퓨팅)', color: C.green },
  { name: 'Kati 1B',      mw: 35,  type: '준공 중',    color: C.yellow },
  { name: 'Dorothy 1A',   mw: 20,  type: '운영(컴퓨팅)', color: C.green },
  { name: 'Dorothy 1B',   mw: 17,  type: '운영(컴퓨팅)', color: C.green },
  { name: 'Kati 2',       mw: 350, type: '계획',       color: C.blue },
  { name: 'Dorothy 3',    mw: 300, type: '계획',       color: C.blue },
]

const pipelineVsOps = [
  { name: 'SLNH', 운영: 235, 계획: 650 },
  { name: 'IREN', 운영: 660, 계획: 2090 },
]

const financials = [
  { quarter: 'Q1 25', revenue: 5.1,  loss: -14.2 },
  { quarter: 'Q2 25', revenue: 6.3,  loss: -18.7 },
  { quarter: 'Q3 25', revenue: 7.8,  loss: -20.1 },
  { quarter: 'Q4 25', revenue: 10.5, loss: -16.0 },
  { quarter: 'Q1 26E', revenue: 13.2, loss: -12.5 },
]

const dilutionData = [
  { name: '기존 주주', shares: 141.3, color: C.blue },
  { name: 'SEPA 잠재 희석 (YA II)', shares: 26.5, color: C.red },
  { name: '추가 등록', shares: 2.5, color: C.orange },
]

const riskRadar = [
  { factor: '희석 리스크',  SLNH: 90, IREN: 20 },
  { factor: '재무 건전성',  SLNH: 15, IREN: 70 },
  { factor: '실행 역량',    SLNH: 35, IREN: 80 },
  { factor: '테마 적합성',  SLNH: 95, IREN: 90 },
  { factor: '성장 잠재력',  SLNH: 85, IREN: 75 },
  { factor: '상장 안정성',  SLNH: 30, IREN: 85 },
]

const priceHistory = [
  { date: "'24 Q3", price: 2.8 },
  { date: "'24 Q4", price: 1.4 },
  { date: "'25 Q1", price: 0.8 },
  { date: "'25 Q2", price: 0.55 },
  { date: "'25 Q3", price: 0.72 },
  { date: "'25 Q4", price: 1.05 },
  { date: "'26 Q1", price: 0.62 },
  { date: "'26 Apr", price: 1.05 },
  { date: "'26 May", price: 1.54 },
]

const catalysts = [
  { date: '2025.05', event: 'Nasdaq $1 경고 1차', type: 'risk' },
  { date: '2025.10', event: '컴플라이언스 1차 회복', type: 'pos' },
  { date: '2025.12', event: 'Generate Capital $100M 신용 확보', type: 'pos' },
  { date: '2026.02', event: 'Kati 1 83MW 가동 시작', type: 'pos' },
  { date: '2026.04', event: 'Briscoe 풍력 150MW $53M 인수', type: 'pos' },
  { date: '2026.04', event: 'Dorothy 1A 완전 지분 인수 ($16.5M)', type: 'pos' },
  { date: '2026.04', event: '26.5M주 재매각 등록 (SEPA 위험)', type: 'risk' },
  { date: '2026.05', event: '컴플라이언스 2차 회복 발표', type: 'pos' },
]

const valuationComp = [
  { metric: '시가총액 ($M)',      SLNH: 228,  IREN: 1820 },
  { metric: '운영 MW',           SLNH: 235,  IREN: 660  },
  { metric: 'MW당 시총 ($M/MW)', SLNH: 0.97, IREN: 2.76 },
  { metric: '매출 ($M, TTM)',    SLNH: 29.7, IREN: 185  },
  { metric: '파이프라인 (GW)',    SLNH: 4.3,  IREN: 2.75 },
]

// ── 공통 컴포넌트 ─────────────────────────────────────────
const Card = ({ children, style = {} }) => (
  <div style={{
    background: C.cardBg, border: `1px solid ${C.border}`,
    borderRadius: 12, padding: 20, ...style
  }}>
    {children}
  </div>
)

const Badge = ({ children, color = C.blue }) => (
  <span style={{
    background: color + '22', color, border: `1px solid ${color}55`,
    borderRadius: 6, padding: '2px 10px', fontSize: 11, fontWeight: 700,
  }}>
    {children}
  </span>
)

const StatBox = ({ label, value, sub, color = C.text }) => (
  <div style={{ textAlign: 'center' }}>
    <div style={{ color, fontSize: 24, fontWeight: 800, lineHeight: 1 }}>{value}</div>
    <div style={{ color: C.muted, fontSize: 11, marginTop: 4 }}>{label}</div>
    {sub && <div style={{ color: C.gray, fontSize: 10, marginTop: 2 }}>{sub}</div>}
  </div>
)

const SectionTitle = ({ children, sub }) => (
  <div style={{ marginBottom: 16 }}>
    <h2 style={{ color: C.text, fontSize: 15, fontWeight: 700, margin: 0 }}>{children}</h2>
    {sub && <p style={{ color: C.muted, fontSize: 11, margin: '3px 0 0' }}>{sub}</p>}
  </div>
)

const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#0f172a', border: `1px solid ${C.border}`, borderRadius: 8, padding: '8px 12px' }}>
      <p style={{ color: C.muted, fontSize: 11, margin: '0 0 4px' }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color, fontSize: 12, fontWeight: 600, margin: '2px 0' }}>
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  )
}

// ── 메인 ─────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState('overview')

  const tabs = [
    { id: 'overview',  label: '📊 종합 현황' },
    { id: 'capacity',  label: '⚡ 전력/MW' },
    { id: 'financial', label: '💰 재무' },
    { id: 'risk',      label: '⚠️ 리스크' },
    { id: 'compare',   label: '🆚 IREN 비교' },
  ]

  const grid2 = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }
  const spanAll = { gridColumn: '1 / -1' }

  return (
    <div style={{ background: C.darkBg, minHeight: '100vh', fontFamily: 'system-ui, sans-serif', color: C.text }}>

      {/* ── 헤더 ── */}
      <div style={{ background: 'linear-gradient(135deg,#0f172a,#1e293b)', borderBottom: `1px solid ${C.border}`, padding: '24px 32px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
            <div style={{ background: C.green + '22', border: `2px solid ${C.green}`, borderRadius: 10, padding: '6px 14px' }}>
              <span style={{ color: C.green, fontWeight: 800, fontSize: 20 }}>SLNH</span>
            </div>
            <div>
              <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>Soluna Holdings</h1>
              <p style={{ margin: 0, color: C.muted, fontSize: 12 }}>재생에너지 기반 AI/BTC 데이터센터 · NASDAQ</p>
            </div>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <Badge color={C.yellow}>마이크로캡</Badge>
              <Badge color={C.orange}>SEPA 희석 주의</Badge>
              <Badge color={C.green}>Nasdaq 컴플라이언스 회복</Badge>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 16 }}>
            <StatBox label="현재가 (5/7)" value="$1.54" sub="↑ +4.52%" color={C.green} />
            <StatBox label="52주 저점" value="$0.42" sub="상장폐지 위기" color={C.red} />
            <StatBox label="52주 고점" value="$5.14" color={C.cyan} />
            <StatBox label="1개월 수익률" value="+128%" color={C.green} />
            <StatBox label="시가총액" value="$228M" sub="마이크로캡" />
            <StatBox label="애널 목표가" value="$5.00" sub="+224% 업사이드" color={C.purple} />
          </div>
        </div>
      </div>

      {/* ── 탭 ── */}
      <div style={{ borderBottom: `1px solid ${C.border}`, background: C.cardBg, padding: '0 32px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', gap: 2 }}>
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              background: tab === t.id ? C.blue + '22' : 'transparent',
              color: tab === t.id ? C.blue : C.muted,
              border: 'none', borderBottom: tab === t.id ? `2px solid ${C.blue}` : '2px solid transparent',
              padding: '13px 16px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── 콘텐츠 ── */}
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 32px' }}>

        {/* ═══ 탭1: 종합 현황 ═══ */}
        {tab === 'overview' && (
          <div style={grid2}>
            <div style={spanAll}>
              <Card>
                <SectionTitle sub="2025~2026 주가 흐름 + Nasdaq 컴플라이언스 이벤트">주가 흐름</SectionTitle>
                <ResponsiveContainer width="100%" height={190}>
                  <AreaChart data={priceHistory}>
                    <defs>
                      <linearGradient id="pg" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={C.cyan} stopOpacity={0.3}/>
                        <stop offset="95%" stopColor={C.cyan} stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border}/>
                    <XAxis dataKey="date" tick={{ fill: C.muted, fontSize: 11 }}/>
                    <YAxis tick={{ fill: C.muted, fontSize: 11 }} tickFormatter={v=>`$${v}`} domain={[0,6]}/>
                    <Tooltip content={<Tip/>} formatter={v=>[`$${v}`,'주가']}/>
                    <ReferenceLine y={1.0} stroke={C.red} strokeDasharray="4 4"
                      label={{ value:'Nasdaq $1 기준선', fill: C.red, fontSize: 10, position:'insideTopRight' }}/>
                    <Area type="monotone" dataKey="price" stroke={C.cyan} fill="url(#pg)" strokeWidth={2} name="주가"/>
                  </AreaChart>
                </ResponsiveContainer>
              </Card>
            </div>

            <Card>
              <SectionTitle>주요 이벤트 타임라인</SectionTitle>
              <div style={{ display:'flex', flexDirection:'column', gap:9 }}>
                {catalysts.map((c,i)=>(
                  <div key={i} style={{ display:'flex', alignItems:'center', gap:10 }}>
                    <span style={{ color:C.muted, fontSize:10, minWidth:58, fontFamily:'monospace' }}>{c.date}</span>
                    <div style={{ width:7,height:7,borderRadius:'50%',background:c.type==='risk'?C.red:C.green,flexShrink:0 }}/>
                    <span style={{ fontSize:12, color:c.type==='risk'?C.red:C.text }}>{c.event}</span>
                  </div>
                ))}
              </div>
            </Card>

            <Card>
              <SectionTitle sub="3단 수직통합 비즈니스 모델">사업 구조</SectionTitle>
              {[
                { icon:'🌬️', label:'재생에너지 생산', desc:'Briscoe 풍력 150MW 직접 소유', color:C.green },
                { icon:'🖥️', label:'데이터센터 운영',  desc:'BTC 채굴 + AI/HPC 컴퓨팅',     color:C.blue },
                { icon:'💡', label:'연산 서비스 판매', desc:'호스팅 파트너 + AI 고객 유치',   color:C.purple },
              ].map((s,i)=>(
                <div key={i} style={{ display:'flex',alignItems:'center',gap:12,padding:'11px 0',borderBottom:i<2?`1px solid ${C.border}`:'none' }}>
                  <span style={{ fontSize:26 }}>{s.icon}</span>
                  <div>
                    <Badge color={s.color}>{s.label}</Badge>
                    <div style={{ color:C.muted,fontSize:11,marginTop:4 }}>{s.desc}</div>
                  </div>
                </div>
              ))}
              <div style={{ marginTop:14,padding:10,background:C.green+'11',borderRadius:8,border:`1px solid ${C.green}33` }}>
                <p style={{ color:C.green,fontSize:11,margin:0,fontWeight:600 }}>
                  ✅ 핵심 경쟁력: 자체 발전 → 전기 원가 ≈ $0 → 연산 마진 구조적 우위
                </p>
              </div>
            </Card>
          </div>
        )}

        {/* ═══ 탭2: 전력/MW ═══ */}
        {tab === 'capacity' && (
          <div style={grid2}>
            <div style={spanAll}>
              <Card>
                <SectionTitle sub="프로젝트별 MW 용량 — 운영 / 준공 / 계획">전력 용량 전체 현황</SectionTitle>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={mwData} margin={{ bottom:10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border}/>
                    <XAxis dataKey="name" tick={{ fill:C.muted,fontSize:11 }} interval={0}/>
                    <YAxis tick={{ fill:C.muted,fontSize:11 }} tickFormatter={v=>`${v}MW`}/>
                    <Tooltip content={<Tip/>} formatter={v=>[`${v} MW`,'용량']}/>
                    <Bar dataKey="mw" name="용량(MW)" radius={[6,6,0,0]}>
                      {mwData.map((e,i)=><Cell key={i} fill={e.color}/>)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div style={{ display:'flex',gap:18,justifyContent:'center',marginTop:8 }}>
                  {[['운영 중',C.green],['준공 중',C.yellow],['계획',C.blue]].map(([l,c])=>(
                    <div key={l} style={{ display:'flex',alignItems:'center',gap:6 }}>
                      <div style={{ width:10,height:10,borderRadius:3,background:c }}/>
                      <span style={{ color:C.muted,fontSize:11 }}>{l}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>

            <Card>
              <SectionTitle sub="실제 가동 vs 계획 MW 비율 (SLNH vs IREN)">운영 vs 파이프라인</SectionTitle>
              <ResponsiveContainer width="100%" height={210}>
                <BarChart data={pipelineVsOps}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border}/>
                  <XAxis dataKey="name" tick={{ fill:C.muted,fontSize:13 }}/>
                  <YAxis tick={{ fill:C.muted,fontSize:11 }} tickFormatter={v=>`${v}MW`}/>
                  <Tooltip content={<Tip/>}/>
                  <Legend wrapperStyle={{ color:C.muted,fontSize:12 }}/>
                  <Bar dataKey="운영" fill={C.green} radius={[4,4,0,0]}/>
                  <Bar dataKey="계획" fill={C.blue}  radius={[4,4,0,0]}/>
                </BarChart>
              </ResponsiveContainer>
              <div style={{ marginTop:12,padding:10,background:C.yellow+'11',borderRadius:8,border:`1px solid ${C.yellow}33` }}>
                <p style={{ color:C.yellow,fontSize:11,margin:0 }}>
                  ⚠️ SLNH 전체 4.3GW 중 실가동 ~235MW = 5.5% — 파이프라인이 주가 선반영
                </p>
              </div>
            </Card>

            <Card>
              <SectionTitle sub="Briscoe 150MW 풍력 단지 — $53M 인수 재무 효과">핵심 자산: Briscoe 풍력</SectionTitle>
              {[
                { label:'취득가',              value:'$53M',       color:C.red    },
                { label:'예상 연간 매출',       value:'$20~24.4M',  color:C.green  },
                { label:'예상 1년차 EBITDA',   value:'$6~11M',     color:C.green  },
                { label:'취득가 회수 기간',     value:'~6~7년',     color:C.yellow },
                { label:'P/EBITDA (인수 기준)', value:'~6.2x',      color:C.blue   },
                { label:'전기 원가',            value:'≈ $0',       color:C.green  },
              ].map((r,i)=>(
                <div key={i} style={{ display:'flex',justifyContent:'space-between',alignItems:'center',padding:'9px 0',borderBottom:i<5?`1px solid ${C.border}`:'none' }}>
                  <span style={{ color:C.muted,fontSize:12 }}>{r.label}</span>
                  <span style={{ color:r.color,fontWeight:700,fontSize:13 }}>{r.value}</span>
                </div>
              ))}
            </Card>
          </div>
        )}

        {/* ═══ 탭3: 재무 ═══ */}
        {tab === 'financial' && (
          <div style={grid2}>
            <div style={spanAll}>
              <Card>
                <SectionTitle sub="분기별 매출 vs 순손실 ($M)">매출 vs 순손실 추이</SectionTitle>
                <ResponsiveContainer width="100%" height={230}>
                  <BarChart data={financials}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.border}/>
                    <XAxis dataKey="quarter" tick={{ fill:C.muted,fontSize:11 }}/>
                    <YAxis tick={{ fill:C.muted,fontSize:11 }} tickFormatter={v=>`$${v}M`}/>
                    <Tooltip content={<Tip/>} formatter={v=>[`$${v}M`]}/>
                    <Legend wrapperStyle={{ color:C.muted,fontSize:12 }}/>
                    <ReferenceLine y={0} stroke={C.border}/>
                    <Bar dataKey="revenue" name="매출 ($M)"   fill={C.green} radius={[4,4,0,0]}/>
                    <Bar dataKey="loss"    name="순손실 ($M)" fill={C.red}   radius={[4,4,0,0]}/>
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </div>

            <Card>
              <SectionTitle sub="TTM 기준">핵심 재무 지표</SectionTitle>
              {[
                { label:'연간 매출',       value:'$29.7M',  color:C.green  },
                { label:'영업손실',        value:'-$49.6M', color:C.red    },
                { label:'순손실',          value:'-$69M',   color:C.red    },
                { label:'EBIT 마진',       value:'-167%',   color:C.red    },
                { label:'순이익 마진',     value:'-192%',   color:C.red    },
                { label:'분기 잉여현금흐름', value:'-$16.8M', color:C.red  },
                { label:'유동비율',        value:'1.9x',    color:C.green  },
                { label:'P/S',             value:'5.8x',    color:C.yellow },
              ].map((r,i)=>(
                <div key={i} style={{ display:'flex',justifyContent:'space-between',padding:'8px 0',borderBottom:i<7?`1px solid ${C.border}`:'none' }}>
                  <span style={{ color:C.muted,fontSize:12 }}>{r.label}</span>
                  <span style={{ color:r.color,fontWeight:700 }}>{r.value}</span>
                </div>
              ))}
            </Card>

            <Card>
              <SectionTitle sub="연간 ~$67M 소각 vs 조달 구조">현금 소각 & 조달</SectionTitle>
              <div style={{ padding:12,background:C.red+'11',borderRadius:8,border:`1px solid ${C.red}33`,marginBottom:14 }}>
                <p style={{ color:C.red,fontSize:13,margin:0,fontWeight:600 }}>
                  연간 현금 소각 ~$67M<br/>
                  <span style={{ fontWeight:400,fontSize:11 }}>매출 대비 소각률: 225%</span>
                </p>
              </div>
              {[
                { src:'Generate Capital 신용',  amt:'$100M',     color:C.blue,  note:'확보 완료' },
                { src:'SEPA (YA II)',            amt:'$25M',      color:C.red,   note:'희석 조건부' },
                { src:'Briscoe 신규 매출',       amt:'$20~24M/년', color:C.green, note:'2026 가산' },
                { src:'기존 호스팅 매출',         amt:'$29.7M/년', color:C.green, note:'TTM' },
              ].map((r,i)=>(
                <div key={i} style={{ display:'flex',justifyContent:'space-between',alignItems:'center',padding:'9px 0',borderBottom:i<3?`1px solid ${C.border}`:'none' }}>
                  <div>
                    <div style={{ color:C.text,fontSize:12 }}>{r.src}</div>
                    <div style={{ color:C.muted,fontSize:11 }}>{r.note}</div>
                  </div>
                  <Badge color={r.color}>{r.amt}</Badge>
                </div>
              ))}
            </Card>
          </div>
        )}

        {/* ═══ 탭4: 리스크 ═══ */}
        {tab === 'risk' && (
          <div style={grid2}>
            <Card>
              <SectionTitle sub="발행주식 대비 잠재 희석 비율">SEPA 희석 구조</SectionTitle>
              <div style={{ display:'flex',justifyContent:'center' }}>
                <PieChart width={240} height={200}>
                  <Pie data={dilutionData} cx="50%" cy="50%" outerRadius={85} dataKey="shares"
                    label={({percent})=>`${(percent*100).toFixed(1)}%`} labelLine={false}>
                    {dilutionData.map((e,i)=><Cell key={i} fill={e.color}/>)}
                  </Pie>
                  <Tooltip formatter={v=>[`${v}M주`]}/>
                </PieChart>
              </div>
              <div style={{ display:'flex',flexDirection:'column',gap:7,marginTop:8 }}>
                {dilutionData.map((d,i)=>(
                  <div key={i} style={{ display:'flex',alignItems:'center',gap:10 }}>
                    <div style={{ width:10,height:10,borderRadius:3,background:d.color }}/>
                    <span style={{ color:C.muted,fontSize:12,flex:1 }}>{d.name}</span>
                    <span style={{ color:d.color,fontWeight:700,fontSize:12 }}>{d.shares}M주</span>
                  </div>
                ))}
              </div>
              <div style={{ marginTop:14,padding:10,background:C.red+'11',borderRadius:8,border:`1px solid ${C.red}33` }}>
                <p style={{ color:C.red,fontSize:11,margin:0 }}>
                  ⚠️ 잠재 희석률 +20.5% — 주가 상승 시 YA II 매도 압력 구조
                </p>
              </div>
            </Card>

            <Card>
              <SectionTitle sub="$1 최저가 기준 위반 이력 — 두 번의 상장폐지 위기">Nasdaq 상장 안정성</SectionTitle>
              {[
                { date:'2025.05.08', event:'1차 경고', detail:'30영업일 연속 $1 미만',       color:C.red,   icon:'🚨' },
                { date:'2025.10.06', event:'1차 회복', detail:'10영업일 $1 이상 유지',       color:C.green, icon:'✅' },
                { date:'2026 Q1',    event:'2차 위기', detail:'주가 $0.42까지 하락',        color:C.red,   icon:'🚨' },
                { date:'2026.04.30', event:'2차 회복', detail:'4/14~4/29 $1 이상 유지',    color:C.green, icon:'✅' },
                { date:'2026.05.01', event:'공식 발표', detail:'Nasdaq 서한 수령 완료',     color:C.green, icon:'📄' },
              ].map((e,i)=>(
                <div key={i} style={{ display:'flex',gap:12,padding:'9px 0',borderBottom:i<4?`1px solid ${C.border}`:'none' }}>
                  <span style={{ fontSize:16 }}>{e.icon}</span>
                  <div>
                    <div style={{ color:C.muted,fontSize:10,fontFamily:'monospace' }}>{e.date}</div>
                    <div style={{ color:e.color,fontSize:12,fontWeight:600 }}>{e.event}</div>
                    <div style={{ color:C.gray,fontSize:11 }}>{e.detail}</div>
                  </div>
                </div>
              ))}
              <div style={{ marginTop:12,padding:10,background:C.orange+'11',borderRadius:8,border:`1px solid ${C.orange}33` }}>
                <p style={{ color:C.orange,fontSize:11,margin:0 }}>
                  ⚠️ 두 번의 위기 → 기관투자자 내부규정 투자 불가 / ETF 편입 불가
                </p>
              </div>
            </Card>

            <div style={spanAll}>
              <Card>
                <SectionTitle sub="핵심 리스크 vs 기회 요인">Bull / Bear 케이스</SectionTitle>
                <div style={grid2}>
                  <div>
                    <div style={{ color:C.red,fontSize:14,fontWeight:700,marginBottom:12 }}>🐻 Bear Case</div>
                    {[
                      'SEPA 희석으로 주가 상승 천장 구조적 형성',
                      '두 번의 상장폐지 위기 → 기관 신뢰도 훼손',
                      '매출 대비 2배 이상 손실 → 자립 불가',
                      '4.3GW 파이프라인 중 5.5%만 실가동',
                      'AI 수익화는 아직 계획 단계',
                    ].map((r,i)=>(
                      <div key={i} style={{ display:'flex',gap:8,marginBottom:8 }}>
                        <span style={{ color:C.red }}>✗</span>
                        <span style={{ color:C.muted,fontSize:12 }}>{r}</span>
                      </div>
                    ))}
                  </div>
                  <div>
                    <div style={{ color:C.green,fontSize:14,fontWeight:700,marginBottom:12 }}>🐂 Bull Case</div>
                    {[
                      '자체 발전 = 전기 원가 0 → 구조적 마진 우위',
                      'Dorothy 3 / Kati 2 AI 고객 실계약 체결 시',
                      '4.3GW 파이프라인 = 성장 옵션 가치',
                      'IREN 대비 MW당 시총 65% 할인 상태',
                      'SEPA 상환 완료 시 희석 구조 종료',
                    ].map((r,i)=>(
                      <div key={i} style={{ display:'flex',gap:8,marginBottom:8 }}>
                        <span style={{ color:C.green }}>✓</span>
                        <span style={{ color:C.muted,fontSize:12 }}>{r}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </Card>
            </div>
          </div>
        )}

        {/* ═══ 탭5: IREN 비교 ═══ */}
        {tab === 'compare' && (
          <div style={grid2}>
            <Card>
              <SectionTitle sub="6개 항목 정성 평가 (100점 만점)">SLNH vs IREN 종합 비교</SectionTitle>
              <ResponsiveContainer width="100%" height={280}>
                <RadarChart data={riskRadar}>
                  <PolarGrid stroke={C.border}/>
                  <PolarAngleAxis dataKey="factor" tick={{ fill:C.muted,fontSize:11 }}/>
                  <Radar name="SLNH" dataKey="SLNH" stroke={C.cyan}   fill={C.cyan}   fillOpacity={0.2} strokeWidth={2}/>
                  <Radar name="IREN" dataKey="IREN" stroke={C.orange} fill={C.orange} fillOpacity={0.15} strokeWidth={2}/>
                  <Legend wrapperStyle={{ color:C.muted,fontSize:12 }}/>
                  <Tooltip/>
                </RadarChart>
              </ResponsiveContainer>
            </Card>

            <Card>
              <SectionTitle sub="주요 정량 지표 바 비교">핵심 지표 비교</SectionTitle>
              {valuationComp.map((v,i)=>{
                const maxV = Math.max(v.SLNH, v.IREN)
                return (
                  <div key={i} style={{ marginBottom:14 }}>
                    <div style={{ color:C.muted,fontSize:11,marginBottom:5 }}>{v.metric}</div>
                    {[{label:'SLNH',val:v.SLNH,color:C.cyan},{label:'IREN',val:v.IREN,color:C.orange}].map(({label,val,color})=>(
                      <div key={label} style={{ marginBottom:4 }}>
                        <div style={{ display:'flex',justifyContent:'space-between',marginBottom:2 }}>
                          <span style={{ color,fontSize:11,fontWeight:700 }}>{label}</span>
                          <span style={{ color,fontSize:11 }}>{val < 10 ? val.toFixed(2) : val.toLocaleString()}</span>
                        </div>
                        <div style={{ background:C.border,borderRadius:4,height:6 }}>
                          <div style={{ width:`${(val/maxV)*100}%`,background:color,borderRadius:4,height:'100%' }}/>
                        </div>
                      </div>
                    ))}
                  </div>
                )
              })}
            </Card>

            <div style={spanAll}>
              <Card>
                <SectionTitle>"제2의 IREN" 가능성 — 최종 판단</SectionTitle>
                <div style={{ display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:16 }}>
                  {[
                    { title:'지금 당장',  score:'❌ 아직 아님',   color:C.red,
                      desc:'IREN은 660MW 실가동+수익성. SLNH는 235MW+적자. 같은 테마지만 실행력 차이 큼.' },
                    { title:'1~2년 후',  score:'⚠️ 조건부 가능', color:C.yellow,
                      desc:'Dorothy 3 AI 계약 + Kati 2 착공 + SEPA 해소 = IREN 수준 재평가. $5+ 가능.' },
                    { title:'투자 포지션', score:'🎲 소액 투기적',  color:C.blue,
                      desc:'포트 2~3% 이하. 손절 $1. Dorothy 3 계약이 핵심 트리거. 분할매수 필수.' },
                  ].map((c,i)=>(
                    <div key={i} style={{ padding:16,background:c.color+'11',borderRadius:10,border:`1px solid ${c.color}33` }}>
                      <div style={{ color:C.muted,fontSize:11,marginBottom:5 }}>{c.title}</div>
                      <div style={{ color:c.color,fontSize:14,fontWeight:800,marginBottom:8 }}>{c.score}</div>
                      <div style={{ color:C.muted,fontSize:12,lineHeight:1.5 }}>{c.desc}</div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        )}
      </div>

      <div style={{ borderTop:`1px solid ${C.border}`,padding:'14px 32px',textAlign:'center' }}>
        <p style={{ color:C.gray,fontSize:11,margin:0 }}>
          ⚠️ 본 자료는 교육 목적의 브레인스토밍이며 투자 권고가 아닙니다. 데이터 기준: 2026년 5월 10일
        </p>
      </div>
    </div>
  )
}
