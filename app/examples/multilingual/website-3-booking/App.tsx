import { useState, useEffect, useCallback, useRef, type FormEvent, type CSSProperties } from "react";

type Destination = {
  id: string;
  name: string;
  price: number;
  color: string;
};

const destinations: Destination[] = [
  { id: "1", name: "Kyoto", price: 899, color: "#2c5f7e" },
  { id: "2", name: "Paris", price: 1299, color: "#e67e22" },
  { id: "3", name: "Rome", price: 999, color: "#c0392b" },
  { id: "4", name: "Tokyo", price: 1199, color: "#8e44ad" },
  { id: "5", name: "Cairo", price: 799, color: "#27ae60" },
  { id: "6", name: "Singapore", price: 1099, color: "#2980b9" },
];

const categories = ["All", "Europe", "Asia", "Africa"];

const categoryMap: Record<string, number[]> = {
  All: [1, 2, 3, 4, 5, 6],
  Europe: [2, 3],
  Asia: [1, 4, 6],
  Africa: [5],
};

const sortOptions = ["Recommended", "Price: Low to High", "Price: High to Low"];

type Booking = { id: string; name: string; destination: string; date: string; guests: number; price: number };
function readFavorites(): string[] {
  try { const value=JSON.parse(localStorage.getItem('atlas-favorites')||'[]');
    return Array.isArray(value)? [...new Set<string>(value.filter((id:unknown):id is string=>typeof id==='string'&&destinations.some(dest=>dest.id===id)))]:[];
  } catch { return []; }
}
function readBookings(): Booking[] {
  try { const value=JSON.parse(localStorage.getItem('atlas-bookings')||'[]');
    return Array.isArray(value)? value.filter((item:Booking)=>item&&typeof item.id==='string'&&typeof item.name==='string'&&typeof item.destination==='string'&&typeof item.date==='string'&&Number.isInteger(item.guests)&&item.guests>=1&&item.guests<=8&&Number.isFinite(item.price)&&item.price>0):[];
  } catch { return []; }
}

export default function App() {
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("All");
  const [sort, setSort] = useState(0);
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [favorites, setFavorites] = useState<string[]>(readFavorites);
  const [selectedDestination, setSelectedDestination] = useState<Destination | null>(null);
  const [traveler, setTraveler] = useState("");
  const [email, setEmail] = useState("");
  const [date, setDate] = useState("");
  const [guests, setGuests] = useState(1);
  const [status, setStatus] = useState("");
  const [bookingHistory, setBookingHistory] = useState<Booking[]>(readBookings);
  const dialogRef=useRef<HTMLDialogElement>(null);
  const openerRef=useRef<HTMLElement|null>(null);
  useEffect(()=>{
    try{ localStorage.setItem('atlas-favorites',JSON.stringify(favorites)); }
    catch{ setStatus('Local storage is unavailable; saved destinations will not survive reload.'); }
  },[favorites]);
  useEffect(()=>{
    try{ localStorage.setItem('atlas-bookings',JSON.stringify(bookingHistory)); }
    catch{ setStatus('Local storage is unavailable; booking history will not survive reload.'); }
  },[bookingHistory]);
  useEffect(()=>{
    if(!selectedDestination)return;
    const dialog=dialogRef.current;
    dialog?.showModal();dialog?.querySelector<HTMLInputElement>('#traveler')?.focus();
    return()=>{if(dialog?.open)dialog.close();if(openerRef.current?.isConnected)openerRef.current.focus();};
  },[selectedDestination]);

  const handleFavorite = useCallback((id: string) => {
    setFavorites(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  }, []);

  const sortedAndFilteredDestinations = (() => {
    let filtered = destinations;
    if (search.trim()) {
      filtered = filtered.filter(d => d.name.toLowerCase().includes(search.toLowerCase()));
    }
    if (categoryFilter !== "All") {
      filtered = filtered.filter(d => categoryMap[categoryFilter].includes(parseInt(d.id)));
    }
    if(favoritesOnly)filtered=filtered.filter(dest=>favorites.includes(dest.id));
    const sorted = [...filtered];
    if (sort === 1) {
      sorted.sort((a, b) => a.price - b.price);
    } else if(sort === 2) {
      sorted.sort((a, b) => b.price - a.price);
    }
    return filtered.length > 0 ? sorted : [];
  })();

  const handleBook = useCallback((dest: Destination | null) => {
    if (!dest) return;
    openerRef.current=document.activeElement as HTMLElement;
    setSelectedDestination(dest);
    setStatus("");
    setTraveler("");
    setEmail("");
    setDate("");
    setGuests(1);
  }, []);

  const handleCancel = useCallback(() => {
    setSelectedDestination(null);
    setStatus("");
    setTraveler("");
    setEmail("");
    setDate("");
    setGuests(1);
  }, []);

  const handleConfirm = useCallback((e: FormEvent) => {
    e.preventDefault();
    if (!traveler.trim()) {
      setStatus("Please enter a traveler name.");
      return;
    }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setStatus("Please enter a valid email address.");
      return;
    }
    if (!date || date < new Date().toISOString().slice(0,10)) {
      setStatus("Please select a future travel date.");
      return;
    }
    if (!Number.isInteger(guests) || guests < 1 || guests > 8) {
      setStatus("Guests must be between 1 and 8.");
      return;
    }
    if(!selectedDestination)return;
    const newHistoryItem:Booking = {
      id:crypto.randomUUID(),
      destination:selectedDestination.name,
      guests,
      name: traveler.trim(),
      date,
      price: selectedDestination.price * guests,
    };
    setBookingHistory(prev => [...prev, newHistoryItem]);
    setSelectedDestination(null);
    setStatus(`Booking confirmed: ${selectedDestination.name} for ${traveler.trim()}, ${guests} guest(s), $${newHistoryItem.price}. Local demo only.`);
  }, [traveler, email, date, guests, selectedDestination]);

  const heroStyle: CSSProperties = {
    background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    padding: "clamp(2rem, 5vw + 1rem, 4rem) 1.5rem 2rem",
    textAlign: "center",
    color: "#fff",
    borderBottomRightRadius: "2rem",
    overflow: "hidden",
    position: "relative" as const,
  };

  return (
    <>
      <style>{`
        :root { --space: 0.5rem; --surface: #fff; --ink: #172526; --accent: #0d6559; }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, -apple-system, sans-serif; }
        body { min-height: 100vh; background: var(--surface); color: var(--ink); line-height: 1.5; }
        .container { max-width: 1280px; margin: 0 auto; padding: 0 1rem; }
        button { background: var(--accent); color: #fff; border: none; border-radius: 0.375rem; padding: 0.625rem 1rem; font-size: 0.875rem; cursor: pointer; transition: opacity 150ms ease; }
        button:hover { opacity: 0.9; }
        button:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
        .card { background: #fff; border-radius: 0.75rem; padding: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,.1); transition: transform 200ms ease, box-shadow 200ms ease; }
        .card:hover { transform: translateY(-4px); box-shadow: 0 8px 25px rgba(0,0,0,.15); }
        @media (prefers-reduced-motion: reduce) { * { transition-duration: 0 !important; animation-duration: 0 !important; } .card:hover { transform: none; } }
        input, select { width: 100%; padding: 0.625rem; border: 2px solid #dcdcdc; border-radius: 0.375rem; font-size: 0.875rem; margin-top: var(--space); box-sizing: border-box; }
        input:focus, select:focus { border-color: var(--accent); outline: none; }
        .error { color: #c0392b; font-size: 0.75rem; margin-top: var(--space); min-height: 1.25rem; }
        .destination-art{height:200px;border-radius:12px;overflow:hidden;position:relative;margin-bottom:1rem;pointer-events:none}
        .card>button{position:relative;z-index:2}
        .destination-art svg{width:100%;height:100%;position:relative;z-index:1}
        .destination-art::before{content:'';position:absolute;width:120px;height:120px;background:#ffffff33;border-radius:50%;top:10px;left:-20px;filter:blur(12px);animation:drift 7s ease-in-out infinite alternate}
        @keyframes drift{to{transform:translateX(220px) translateY(25px)}}
        dialog{max-width:calc(100% - 2rem);width:440px;margin:auto;max-height:90vh;overflow:auto}
        dialog::backdrop{background:#16252bbb;backdrop-filter:blur(3px)}
        .history{margin-top:2rem;padding:1.5rem;background:#f1f7f5;border-radius:16px}
        .history-row{display:flex;justify-content:space-between;gap:1rem;align-items:center;margin-top:1rem;padding:1rem;background:#fff;border-radius:12px;flex-wrap:wrap}
        .notice{margin-top:1rem;font-weight:600;color:#0d6559}
        .container header input,.container header select{max-width:280px}
        @media(prefers-reduced-motion:reduce){*::before,*::after,*{animation:none!important;transition:none!important}}
        .hero-title { animation: fadeIn 800ms ease-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
      <div className="container">
        <header style={heroStyle}>
          <h1 className="hero-title" style={{ fontSize: "clamp(1.75rem, 6vw + 1rem, 3.5rem)", marginBottom: "1rem", fontWeight: "800", letterSpacing: "-0.02em" }}>Atlas Escapes</h1>
          <p style={{ fontSize: "clamp(0.875rem, 3.5vw, 1.125rem)", opacity: 0.9, marginBottom: "1.5rem", maxWidth: "60ch", marginLeft: "auto", marginRight: "auto" }}>Discover your next unforgettable journey with curated destinations worldwide.</p>
          <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap", marginBottom: "2rem" }}>
            <input id="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search destinations..." aria-label="Search destinations" />
            <select id="categoryFilter" value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)} aria-label="Category filter">
              {categories.map(cat => <option key={cat} value={cat}>{cat}</option>)}
            </select>
            <select id="sort" value={sort} onChange={e => setSort(Number(e.target.value))} aria-label="Sort destinations">
              {sortOptions.map((opt, i) => <option key={i} value={i}>{opt}</option>)}
            </select>
          </div>
          <button id="favoritesFilter" onClick={() => setFavoritesOnly(p => !p)} aria-pressed={favoritesOnly} style={{ padding: "0.5rem 1rem", fontSize: "0.75rem" }}>
            {favoritesOnly ? "Hide Favorites Only" : "Show Favorites Only"} ({favorites.length})
          </button>
        </header>
        <main style={{ padding: "2rem 0" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(min(100%,280px),1fr))", gap: "1.5rem" }}>
            {sortedAndFilteredDestinations.map(dest => (
              <article key={dest.id} className="card" style={{ position: "relative" as const }}>
                <div className="destination-art" style={{background:dest.color}} role="img" aria-label={`Original skyline illustration for ${dest.name}`}>
                  <svg viewBox="0 0 360 200" aria-hidden="true"><circle cx="280" cy="50" r="27" fill="#fff7c2"/><path d="M0 140L90 95L150 130L245 85L360 140V200H0Z" fill="#ffffff33"/><path d="M35 180V100H80V180M95 180V125H140V180M155 180V75H200V180M215 180V115H260V180M275 180V95H325V180" stroke="#ffffff88" strokeWidth="10" fill="#ffffff22"/><path d="M0 190H360" stroke="#fff" strokeWidth="5"/></svg>
                </div>
                <h3 style={{ fontSize: "1.25rem", fontWeight: "700", marginBottom: "0.5rem" }}>{dest.name}</h3>
                <p style={{ color: "#666", marginBottom: "1rem" }}>Starting from ${dest.price.toLocaleString()}</p>
                <button id={dest.id==='1'?'bookFirst':undefined} onClick={() => handleBook(dest)} style={{ width: "100%" }}>Book Now</button>
                <button id={dest.id==='1'?'favoriteFirst':undefined} aria-pressed={favorites.includes(dest.id)} onClick={() => handleFavorite(dest.id)} style={{ position: "absolute", top: "0.75rem", right: "0.75rem", padding: "0.375rem 0.75rem", fontSize: "0.875rem" }}>
                  {favorites.includes(dest.id) ? "Saved" : "Save destination"}
                </button>
              </article>
            ))}
          </div>
          {sortedAndFilteredDestinations.length===0&&<p role="status">No results. Try another filter.</p>}
          <p id="status" role="status" className="notice">{status}</p>
          <section className="history"><h2>My saved trips</h2><p>Local demo history. No travel reservation or payment is made.</p>
            {bookingHistory.length===0&&<p>No bookings yet.</p>}
            {bookingHistory.map(item=><article key={item.id} className="history-row"><div><h3>{item.destination} · {item.name}</h3><p>{item.date} · {item.guests} guest(s) · ${item.price}</p></div><button onClick={()=>setBookingHistory(prev=>prev.filter(other=>other.id!==item.id))}>Cancel</button></article>)}
          </section>
        </main>
        <footer style={{ padding: "2rem 0", textAlign: "center", borderTop: "1px solid #eee", marginTop: "3rem", color: "#666" }}>
          <p>&copy; {new Date().getFullYear()} Atlas Escapes. All rights reserved.</p>
        </footer>
      </div>
      {selectedDestination && (
        <dialog ref={dialogRef} aria-labelledby="dialog-title" onCancel={event=>{event.preventDefault();handleCancel();}} style={{ background: "#fff", borderRadius: "0.75rem", padding: "2rem", boxShadow: "0 25px 50px -12px rgba(0,0,0,.25)", border: "none" }}>
          <h2 id="dialog-title" style={{ fontSize: "1.5rem", marginBottom: "1rem", paddingBottom: "0.75rem", borderBottom: "2px solid #eee" }}>Book {selectedDestination.name}</h2>
          <form noValidate onSubmit={handleConfirm} style={{ display: "flex", flexDirection: "column", gap: "var(--space)" }} aria-labelledby="dialog-title">
            <label htmlFor="traveler">Traveler Name</label>
            <input id="traveler" value={traveler} onChange={e => setTraveler(e.target.value)} placeholder="Enter traveler name" required />
            <label htmlFor="email">Email Address</label>
            <input id="email" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required />
            <label htmlFor="date">Travel Date</label>
            <input id="date" type="date" value={date} onChange={e => setDate(e.target.value)} required />
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space)" }}>
              <label htmlFor="guests">Guests:</label>
              <input id="guests" type="number" min="1" max="8" required value={guests||''} onChange={event=>setGuests(Number(event.target.value))} />
            </div>
            <p style={{ fontSize: "0.875rem", color: "#666", marginBottom: "var(--space)" }}>Total price: ${(selectedDestination.price*guests).toLocaleString()}</p>
            {status && <p className="error" role="alert">{status}</p>}
            <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem" }}>
              <button type="submit" id="confirm">Confirm Booking</button>
              <button type="button" onClick={handleCancel}>Cancel</button>
            </div>
          </form>
        </dialog>
      )}
    </>
  );
}
