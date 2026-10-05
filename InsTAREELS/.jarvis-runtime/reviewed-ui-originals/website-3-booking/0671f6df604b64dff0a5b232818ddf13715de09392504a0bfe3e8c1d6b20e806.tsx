import { useState, useEffect, useCallback } from "react";

type Destination = {
  id: string;
  name: string;
  price: number;
  image: string;
};

const destinations: Destination[] = [
  { id: "1", name: "Kyoto", price: 899, image: "https://placehold.co/600x400/2c5f7e/fff?text=Kyoto" },
  { id: "2", name: "Paris", price: 1299, image: "https://placehold.co/600x400/e67e22/fff?text=Paris" },
  { id: "3", name: "Rome", price: 999, image: "https://placehold.co/600x400/c0392b/fff?text=Rome" },
  { id: "4", name: "Tokyo", price: 1199, image: "https://placehold.co/600x400/8e44ad/fff?text=Tokyo" },
  { id: "5", name: "Cairo", price: 799, image: "https://placehold.co/600x400/27ae60/fff?text=Cairo" },
  { id: "6", name: "Singapore", price: 1099, image: "https://placehold.co/600x400/2980b9/fff?text=Singapore" },
];

const categories = ["All", "Europe", "Asia", "Africa"];

const categoryMap: Record<string, number[]> = {
  All: [1, 2, 3, 4, 5, 6],
  Europe: [2, 3],
  Asia: [1, 4, 6],
  Africa: [5],
};

const sortOptions = ["Price: Low to High", "Price: High to Low"];

function getLocalStorageKey(): string {
  const baseUrl = window.location.origin;
  return `${baseUrl}/favorites`;
}

export default function App() {
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("All");
  const [sort, setSort] = useState(0);
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [favorites, setFavorites] = useState<string[]>([]);
  const [selectedDestination, setSelectedDestination] = useState<Destination | null>(null);
  const [traveler, setTraveler] = useState("");
  const [email, setEmail] = useState("");
  const [date, setDate] = useState("");
  const [guests, setGuests] = useState(1);
  const [status, setStatus] = useState("");
  const [bookingHistory, setBookingHistory] = useState<{ name: string; date: string; price: number }[]>([]);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(getLocalStorageKey());
      if (stored) {
        setFavorites(JSON.parse(stored));
      }
      const historyStored = localStorage.getItem("bookingHistory");
      if (historyStored) {
        setBookingHistory(JSON.parse(historyStored));
      }
    } catch {
      // ignore storage errors
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(getLocalStorageKey(), JSON.stringify(favorites));
    } catch {
      // ignore storage errors
    }
  }, [favorites]);

  useEffect(() => {
    try {
      localStorage.setItem("bookingHistory", JSON.stringify(bookingHistory));
    } catch {
      // ignore storage errors
    }
  }, [bookingHistory]);

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
    const sorted = [...filtered];
    if (sort === 0) {
      sorted.sort((a, b) => a.price - b.price);
    } else {
      sorted.sort((a, b) => b.price - a.price);
    }
    return filtered.length > 0 ? sorted : [];
  })();

  const handleBook = useCallback((dest: Destination | null) => {
    if (!dest) return;
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

  const handleConfirm = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!traveler.trim()) {
      setStatus("Please enter a traveler name.");
      return;
    }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setStatus("Please enter a valid email address.");
      return;
    }
    if (!date) {
      setStatus("Please select a date.");
      return;
    }
    if (guests < 1 || guests > 8) {
      setStatus("Guests must be between 1 and 8.");
      return;
    }
    const newHistoryItem = {
      name: traveler.trim(),
      date,
      price: selectedDestination?.price ?? 0,
    };
    setBookingHistory(prev => [...prev, newHistoryItem]);
    setSelectedDestination(null);
    setStatus("Booking confirmed");
  }, [traveler, email, date, guests, selectedDestination]);

  const heroStyle: React.CSSProperties = {
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
          <button id="favoritesFilter" onClick={() => setFavoritesOnly(p => !p)} style={{ position: "absolute", top: "1.5rem", right: "1.5rem", padding: "0.5rem 1rem", fontSize: "0.75rem" }}>
            {favoritesOnly ? "Hide Favorites Only" : "Show Favorites Only"} ({favorites.length})
          </button>
        </header>
        <main style={{ padding: "2rem 0" }}>
          <div style={{ display: "grid", gridTemplateColumns: `repeat(auto-fill, minmax(min(30ch, 1fr), 1fr))`, gap: "1.5rem" }}>
            {sortedAndFilteredDestinations.map(dest => (
              <article key={dest.id} className="card" style={{ position: "relative" as const }}>
                <img src={dest.image} alt={`${dest.name} destination`} style={{ width: "100%", height: "240px", objectFit: "cover", borderRadius: "0.5rem", marginBottom: "1rem" }} />
                <h3 style={{ fontSize: "1.25rem", fontWeight: "700", marginBottom: "0.5rem" }}>{dest.name}</h3>
                <p style={{ color: "#666", marginBottom: "1rem" }}>Starting from ${dest.price.toLocaleString()}</p>
                <button onClick={() => handleBook(dest)} style={{ width: "100%" }}>Book Now</button>
                <button onClick={() => handleFavorite(dest.id)} style={{ position: "absolute", top: "0.75rem", right: "0.75rem", padding: "0.375rem 0.75rem", fontSize: "0.875rem" }}>
                  {favorites.includes(dest.id) ? "â™¥ Favorited" : "â™¡ Favorite"}
                </button>
              </article>
            ))}
          </div>
        </main>
        <footer style={{ padding: "2rem 0", textAlign: "center", borderTop: "1px solid #eee", marginTop: "3rem", color: "#666" }}>
          <p>&copy; {new Date().getFullYear()} Atlas Escapes. All rights reserved.</p>
        </footer>
      </div>
      {selectedDestination && (
        <dialog style={{ background: "#fff", borderRadius: "0.75rem", padding: "2rem", boxShadow: "0 25px 50px -12px rgba(0,0,0,.25)", border: "none" }}>
          <h2 style={{ fontSize: "1.5rem", marginBottom: "1rem", paddingBottom: "0.75rem", borderBottom: "2px solid #eee" }}>Book {selectedDestination.name}</h2>
          <form onSubmit={handleConfirm} style={{ display: "flex", flexDirection: "column", gap: var(--space) }} aria-labelledby="dialog-title">
            <label htmlFor="traveler">Traveler Name</label>
            <input id="traveler" value={traveler} onChange={e => setTraveler(e.target.value)} placeholder="Enter traveler name" required />
            <label htmlFor="email">Email Address</label>
            <input id="email" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required />
            <label htmlFor="date">Travel Date</label>
            <input id="date" type="date" value={date} onChange={e => setDate(e.target.value)} required />
            <div style={{ display: "flex", alignItems: "center", gap: var(--space) }}>
              <label htmlFor="guests">Guests:</label>
              <select id="guests" value={guests} onChange={e => setGuests(Number(e.target.value))}>
                {[...Array(8)].map((_, i) => (
                  <option key={i + 1} value={i + 1}>{i + 1}</option>
                ))}
              </select>
            </div>
            <p style={{ fontSize: "0.875rem", color: "#666", marginBottom: "var(--space)" }}>Total price: ${selectedDestination.price.toLocaleString()}</p>
            {status && <p className="error" id="status">{status}</p>}
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
