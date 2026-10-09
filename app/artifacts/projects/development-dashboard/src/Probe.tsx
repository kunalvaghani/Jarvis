import { useState } from 'react';

export default function Probe() {
  const [count, setCount] = useState(0);

  return (
    <div>
      <p>Probe count {count}</p>
      <button onClick={() => setCount(c => c + 1)}>Add probe</button>
    </div>
  );
}