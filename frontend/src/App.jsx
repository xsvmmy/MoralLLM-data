import React from 'react';
import Visualization from './components/Visualization';
import './App.css';

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>Autonomous Vehicle Ethics Simulator</h1>
        <p className="app-subtitle">
          Configure and visualize ethical dilemmas for autonomous vehicles
        </p>
      </header>

      <main>
        <Visualization />
      </main>
    </div>
  );
}

export default App;
