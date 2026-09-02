import React, { useState } from 'react';

const glyph = (character) => function Glyph({ className = '' }) {
  return <span className={`icon-glyph ${className}`} aria-hidden="true">{character}</span>;
};
const ArrowRight = glyph('→');
const BadgeCheck = glyph('✓');
const Briefcase = glyph('▣');
const Check = glyph('✓');
const Clock3 = glyph('◷');
const Globe2 = glyph('◎');
const Link2 = glyph('⌁');
const Loader2 = glyph('◌');
const MapPin = glyph('⌖');
const ShieldCheck = glyph('◈');
const Sparkles = glyph('✦');
const X = glyph('×');

const viteEnv = import.meta.env;
const isLocalPage = typeof window !== 'undefined' && ['127.0.0.1', 'localhost'].includes(window.location.hostname);
const apiBaseUrl = (viteEnv?.VITE_API_BASE_URL ?? ((viteEnv?.DEV || isLocalPage) ? 'http://127.0.0.1:8000' : '')).replace(/\/$/, '');

function isLinkedInProfileUrl(value) { try { const url = new URL(value.trim()); return /(^|\.)linkedin\.com$/i.test(url.hostname) && /^\/in\/[\w-]+\/?$/i.test(url.pathname); } catch { return false; } }
function initials(name = '') { return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || '?'; }

function normalizeResponse(data) {
  const profile = data.profile ?? {};
  const proxyPath = profile.profileImage?.proxyPath;
  const imageUrl = proxyPath ? `${apiBaseUrl}${proxyPath}` : (profile.profileImage?.url ?? profile.profileImageUrl ?? null);
  return { name: profile.name ?? 'Profile found', headline: profile.headline ?? '', location: profile.location ?? '', imageUrl, imageMeta: profile.profileImage ?? null, experience: Array.isArray(data.experience) ? data.experience : [], certifications: Array.isArray(data.certifications) ? data.certifications : [], skills: Array.isArray(data.skills) ? data.skills : [], languages: Array.isArray(data.languages) ? data.languages : [], sections: data.meta?.sections ?? {}, warnings: data.meta?.warnings ?? [] };
}

async function lookupProfile(linkedinUrl) {
  const response = await fetch(`${apiBaseUrl}/api/v1/profiles`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ linkedinUrl }) });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail ?? body.error?.message ?? 'We could not retrieve that profile.');
  return normalizeResponse(body.data);
}

export default function App() {
  const [url, setUrl] = useState(''); const [status, setStatus] = useState('idle'); const [error, setError] = useState(''); const [profile, setProfile] = useState(null);
  const handleSubmit = async (event) => { event.preventDefault(); setError(''); setProfile(null); if (!isLinkedInProfileUrl(url)) { setStatus('error'); setError('Enter a public LinkedIn profile URL, such as linkedin.com/in/janedoe.'); return; } setStatus('loading'); try { setProfile(await lookupProfile(url.trim())); setStatus('success'); } catch (requestError) { setStatus('error'); setError(requestError.message); } };
  return <main>
    <header className="site-header"><a className="brand" href="#top" aria-label="Profilely home"><span className="brand-mark"><Link2 size={20} strokeWidth={2.6} /></span>profilely</a><nav className="nav-links" aria-label="Main navigation"><a href="#how-it-works">How it works</a><a href="#api">API</a><a href="#privacy">Privacy</a></nav><a className="header-action" href="#lookup">Try it free <ArrowRight size={16} /></a></header>
    <section className="hero" id="top"><div className="eyebrow"><Sparkles size={15} /> LinkedIn profile lookup</div><h1>Professional profiles,<br /><span>made structured.</span></h1><p className="hero-copy">Paste a public LinkedIn profile URL to retrieve verified profile details in one clean response.</p><form className={`lookup-card ${status === 'error' ? 'has-error' : ''}`} id="lookup" onSubmit={handleSubmit} noValidate><label htmlFor="linkedin-url">LinkedIn profile URL</label><div className="input-row"><Link2 className="input-icon" size={20} aria-hidden="true" /><input id="linkedin-url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="linkedin.com/in/janedoe" autoComplete="url" inputMode="url" aria-describedby={error ? 'url-error' : 'url-help'} /><button type="submit" disabled={status === 'loading'}>{status === 'loading' ? <><Loader2 className="spin" size={18} /> Looking up</> : <>Look up profile <ArrowRight size={18} /></>}</button></div>{error ? <p className="form-message error" id="url-error"><X size={15} />{error}</p> : <p className="form-message" id="url-help">Use a public <strong>linkedin.com/in/</strong> profile link. We&apos;ll handle the rest.</p>}</form><div className="trust-row"><span><Check size={16} /> No browser extension</span><span><Check size={16} /> Live API data</span><span><Check size={16} /> Secure requests</span></div></section>
    {profile && <ProfileResult profile={profile} />}
    <section className="feature-strip" id="how-it-works"><div><span className="step-number">01</span><h2>Paste a profile URL</h2><p>We validate and normalize the public LinkedIn URL before processing it.</p></div><div><span className="step-number">02</span><h2>Fetch structured data</h2><p>The API runs one authenticated, sequential profile pipeline.</p></div><div><span className="step-number">03</span><h2>Use verified results</h2><p>Only successfully parsed sections are shown in the result.</p></div></section>
    <footer id="privacy"><span>© 2026 profilely</span><span className="footer-status"><ShieldCheck size={15} /> Credentials stay server-side</span></footer>
  </main>;
}

function ProfileResult({ profile }) {
  const unavailable = Object.entries(profile.sections).filter(([, sectionStatus]) => sectionStatus === 'unavailable' || sectionStatus === 'rsc_fetched_no_data').map(([section]) => section);
  return <section className="result-section" aria-live="polite"><div className="result-heading"><div><span className="result-kicker"><BadgeCheck size={16} /> Profile found</span><h2>Your lookup result</h2></div><button className="new-search" onClick={() => document.getElementById('linkedin-url')?.focus()}>New search</button></div><article className="profile-card"><div className="profile-top">{profile.imageUrl ? <img className="avatar avatar-image" src={profile.imageUrl} alt="" /> : <div className="avatar" aria-hidden="true">{initials(profile.name)}</div>}<div className="profile-intro"><h3>{profile.name}</h3>{profile.headline && <p>{profile.headline}</p>}{profile.location && <span><MapPin size={15} /> {profile.location}</span>}</div><span className="live-pill"><span /> Live data</span></div><div className="profile-grid"><section><p className="section-label"><Briefcase size={15} /> Experience</p>{profile.experience.length ? <div className="timeline">{profile.experience.map((item, index) => <div className="timeline-item" key={`${item.title}-${item.company}-${index}`}><span className="timeline-dot" /><h4>{item.title ?? 'Experience'}</h4><p>{[item.company, item.employmentType, item.dateRange].filter(Boolean).join(' · ')}</p>{(item.location || item.description) && <small>{item.location ?? item.description}</small>}</div>)}</div> : <EmptySection label="Experience is unavailable for this profile." />}</section><section><p className="section-label"><BadgeCheck size={16} /> Certifications</p>{profile.certifications.length ? <div className="certification-list">{profile.certifications.map((item, index) => <div className="certification" key={`${item.name}-${item.issuer}-${index}`}><h4>{item.name}</h4><p>{item.issuer}</p>{(item.issuedDate || item.credentialId) && <small>{[item.issuedDate && `Issued ${item.issuedDate}`, item.credentialId && `ID: ${item.credentialId}`].filter(Boolean).join(' · ')}</small>}</div>)}</div> : <EmptySection label="Certifications are unavailable for this profile." />}</section><section><p className="section-label"><Sparkles size={15} /> Skills</p>{profile.skills.length ? <div className="skills">{profile.skills.map((skill) => <span key={skill}>{skill}</span>)}</div> : <EmptySection label="Skills are unavailable for this profile." />}</section><section><p className="section-label"><Globe2 size={16} /> Languages</p>{profile.languages.length ? <div className="language-list">{profile.languages.map((item) => <div className="language" key={`${item.name}-${item.proficiency}`}><h4>{item.name}</h4><p>{item.proficiency}</p></div>)}</div> : <EmptySection label="Languages are unavailable for this profile." />}</section></div><div className="result-meta"><Clock3 size={14} /> {profile.imageMeta ? `Image verified · ${Number(profile.imageMeta.sizeBytes).toLocaleString()} bytes` : 'Live API response'}{unavailable.length ? ` · Unavailable: ${unavailable.join(', ')}` : ''}</div></article></section>;
}
function EmptySection({ label }) { return <p className="empty-section">{label}</p>; }
