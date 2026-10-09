import { useRef, useState } from 'react';
import { motion, MotionConfig, useReducedMotion } from 'motion/react';

type Project = { id: number; title: string; category: string; owner: string; status: string; progress: number; color: string };
const seed: Project[] = [
  { id: 1, title: 'Studio website', category: 'DESIGN · WEBSITE', owner: 'Amelia', status: 'In progress', progress: 72, color: '#e5efe9' },
  { id: 2, title: 'Mobile onboarding', category: 'PRODUCT · MOBILE', owner: 'Leo', status: 'In progress', progress: 48, color: '#efe9f5' },
  { id: 3, title: 'Brand guidelines', category: 'IDENTITY · SYSTEM', owner: 'Sofia', status: 'Done', progress: 100, color: '#f3ede1' },
  { id: 4, title: 'Customer insights', category: 'RESEARCH · STRATEGY', owner: 'Noah', status: 'Planned', progress: 15, color: '#e7eef5' },
];

export default function App() {
  const [projects, setProjects] = useState(seed);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('All projects');
  const [view, setView] = useState('Overview');
  const [title, setTitle] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [state, setState] = useState('ready');
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const reduce = useReducedMotion();
  const shown = projects.filter(p => p.title.toLowerCase().includes(query.toLowerCase()) && (filter === 'All projects' || p.status === filter));
  const done = projects.filter(p => p.status === 'Done').length;
  function close() { dialog.current?.close(); trigger.current?.focus(); }
  function refresh() { setState('loading'); window.setTimeout(() => setState('ready'), 650); }
  return <MotionConfig reducedMotion="user"><div className="workspace" data-motion={reduce ? 'reduced' : 'full'}>
    <a className="skip" href="#main">Skip to content</a>
    <aside className="sidebar" aria-label="Workspace navigation">
      <a className="brand" href="#main"><span className="brand-mark" aria-hidden="true">f.</span><span>fieldnotes<span className="brand-sub">YOUR SPACE TO MAKE</span></span></a>
      <div className="studio"><span className="studio-avatar" aria-hidden="true">S</span><div>Studio workspace<small>Personal workspace</small></div><span aria-hidden="true">⌄</span></div>
      <p className="nav-label">WORKSPACE</p>
      <nav>{['Overview', 'Projects'].map((name, i) => <button key={name} onClick={() => setView(name)} className={view === name ? 'nav active' : 'nav'} aria-current={view === name ? 'page' : undefined}><span aria-hidden="true">{i ? '▦' : '◈'}</span>{name}{i === 1 && <span className="nav-count" aria-hidden="true">{projects.length}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="tip"><span className="tip-star" aria-hidden="true">✳</span><h3>A little room to focus.</h3><p>Bring your ideas together.<br/>One good step at a time.</p></div><div className="profile"><span className="profile-avatar" aria-hidden="true">AK</span><div>Alex Kim<small>Studio owner</small></div></div></div>
    </aside>
    <main id="main" className="main" aria-label="Main workspace" data-motion={reduce ? "reduced" : "full"}>
      <header className="topbar"><span>Workspace <span aria-hidden="true">/</span> <strong>{view}</strong></span><span className="sample">LOCAL DEMO DATA</span></header>
      <section className="greeting"><div><p className="eyebrow">MAKE SPACE FOR GOOD WORK</p><h1>{view === 'Overview' ? 'A clear view of what’s next.' : 'Ideas, moving forward.'}</h1><p>Your projects, your pace. Here’s where things stand.</p></div><button ref={trigger} className="primary" onClick={() => { setTitle(''); setError(''); dialog.current?.showModal(); }}>+ New project</button></section>
      <div role="status" className="notice" aria-live="polite">{notice}</div>
      {view === 'Overview' && <>
        <section className="stats" aria-label="Project summary">{[
          ['Active projects', String(projects.filter(p => p.status !== 'Done').length).padStart(2, '0'), 'A few things taking shape', '↗'],
          ['Completed', String(done).padStart(2, '0'), 'Good work, delivered', '✓'],
          ['Focus this week', '18.5', 'Hours of thoughtful progress', '◷'],
        ].map(([label, value, caption, icon]) => <motion.article key={label} className="stat" initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .2 }}><div className="stat-top"><h2>{label}</h2><span aria-hidden="true">{icon}</span></div><div className="stat-value">{value}<span>{label === 'Focus this week' ? 'hrs' : ''}</span></div><p>{caption}</p></motion.article>)}</section>
        <section className="insights"><article className="activity"><div className="section-top"><div><p className="eyebrow">STEADY MOMENTUM</p><h2>Your week in focus</h2></div><span className="pill">This week</span></div><div className="chart" role="img" aria-label="Demo focus hours: Monday 2, Tuesday 3, Wednesday 2.5, Thursday 4, Friday 3.5, Saturday 2, Sunday 1.5"><div className="chart-axis"><span>6h</span><span>4h</span><span>2h</span><span>0h</span></div><div className="chart-body"><svg viewBox="0 0 650 160" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#388b73" stopOpacity=".2"/><stop offset="100%" stopColor="#388b73" stopOpacity="0"/></linearGradient></defs><path d="M0 108 C45 108 55 60 105 63 S165 110 210 88 S270 26 320 30 S380 66 430 57 S490 102 540 100 S595 95 650 115 L650 160 L0 160 Z" fill="url(#fill)"/><path d="M0 108 C45 108 55 60 105 63 S165 110 210 88 S270 26 320 30 S380 66 430 57 S490 102 540 100 S595 95 650 115" stroke="#26745e" strokeWidth="3" fill="none"/></svg><div className="chart-days">{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(d => <span key={d}>{d}</span>)}</div></div></div></article><article className="focus-card"><div className="focus-orbit" aria-hidden="true">✳</div><p className="eyebrow">THE BIG PICTURE</p><h2>Progress is a practice.</h2><p>Small steps become great things.<br/>You’re building something good.</p><span className="focus-foot">KEEP THE MOMENTUM ↗</span></article></section>
      </>}
      <section className="projects"><div className="projects-heading"><div><p className="eyebrow">FROM IDEA TO REALITY</p><h2>Your projects <span>{projects.length}</span></h2></div><div className="filters"><label className="search"><span className="sr-only">Search projects</span><input value={query} placeholder="Search projects…" onChange={e => setQuery(e.target.value)}/></label><label><span className="sr-only">Project status</span><select value={filter} onChange={e => setFilter(e.target.value)}>{['All projects','In progress','Planned','Done'].map(x => <option key={x}>{x}</option>)}</select></label></div></div>
        {state === 'loading' ? <p role="status" className="empty">Loading projects…</p> : state === 'error' ? <div className="empty" role="alert"><p>Could not load demo data. Your edits are still here.</p><button className="secondary" onClick={refresh}>Retry</button></div> : shown.length ? <div className="project-grid">{shown.map(p => <motion.article key={p.id} className="project-card" initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .18 }}><div className="project-art" style={{ background: p.color }} aria-hidden="true"><span className={'art-shape shape-' + p.id % 3}></span><span className="art-dot"></span><span className="art-line"></span></div><div className="project-content"><div className="project-meta"><span>{p.category}</span><span className={'status ' + (p.status === 'Done' ? 'done' : '')}>{p.status}</span></div><h3>{p.title}</h3><div className="progress-label"><span>Progress</span><strong>{p.progress}%</strong></div><div className="progress" role="progressbar" aria-label={p.title + ' progress'} aria-valuenow={p.progress} aria-valuemin={0} aria-valuemax={100}><span style={{ width: p.progress + '%' }} /></div><div className="project-bottom"><span className="owner"><span aria-hidden="true">{p.owner.slice(0,1)}</span>{p.owner}</span><button className="text-button" onClick={() => { setProjects(old => old.map(item => item.id === p.id ? { ...item, status: 'Done', progress: 100 } : item)); setNotice(p.title + ' completed'); }} disabled={p.status === 'Done'} aria-label={'Complete ' + p.title}>{p.status === 'Done' ? 'Completed ✓' : 'Mark done ↗'}</button></div></div></motion.article>)}</div> : <div className="empty"><h3>No matching projects</h3><p>Try a different search or status.</p><button className="secondary" onClick={() => { setQuery(''); setFilter('All projects'); }}>Clear filters</button></div>}
      </section>
      <footer><span>Made for a calmer kind of productivity.</span><div><button className="text-button" onClick={refresh}>Refresh data</button><button className="text-button" onClick={() => setState('error')}>Simulate offline</button></div></footer>
    </main>
    <dialog ref={dialog} aria-labelledby="dialog-title" onCancel={() => trigger.current?.focus()}><form noValidate onSubmit={e => { e.preventDefault(); if (!title.trim()) { setError('Enter a project name.'); return; } setProjects(old => [...old, { id: Math.max(...old.map(p => p.id)) + 1, title: title.trim(), category: 'STUDIO · NEW PROJECT', owner: 'Alex', status: 'Planned', progress: 0, color: '#e5efe9' }]); setNotice(title.trim() + ' created'); close(); }}><p className="eyebrow">A NEW BEGINNING</p><h2 id="dialog-title">Make room for an idea.</h2><p>Name your project. The rest can take shape.</p><label htmlFor="project-title">Project name</label><input autoFocus id="project-title" value={title} onChange={e => setTitle(e.target.value)} aria-invalid={!!error} aria-describedby={error ? 'form-error' : undefined} maxLength={80}/>{error && <p id="form-error" role="alert">{error}</p>}<div className="dialog-actions"><button type="button" className="secondary" onClick={close}>Cancel</button><button className="primary" type="submit">Create project</button></div></form></dialog>
  </div></MotionConfig>;
}
