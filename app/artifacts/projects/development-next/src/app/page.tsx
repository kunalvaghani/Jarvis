'use client';
import {useState} from 'react';
export default function App(){const [n,setN]=useState(0);return <main><h1>Next workspace</h1><button onClick={()=>setN(n+1)}>Add task</button><p role="status">Tasks {n}</p></main>;}
