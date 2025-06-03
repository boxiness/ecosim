# Ecosim MVP

**Version 0.8** — Ecosystem simulation with grass, herbivores, and predators.  
Built in Python 3.13 using Pygame, Matplotlib, Tkinter and Perlin noise.

---

## 📖 Overview

Ecosim MVP models a simple toroidal grid world in which:

- **Grass (food)** grows, is eaten by herbivores, and regrows after a fixed number of turns.  
- **Herbivores** move, eat grass, reproduce when they have enough energy, and starve if they run out of energy.  
- **Predators** hunt herbivores, gain energy from each successful hunt, reproduce when they reach a threshold, and starve otherwise.  
- **Rocks** are generated via a Perlin‐noise threshold—herbivores and predators cannot move onto rock tiles.

The population counts of herbivores and predators are plotted live (Lotka–Volterra style) in a Matplotlib window as the simulation runs.

---

## 🚀 Features

1. **Live, interactive chart** of predator vs. herbivore populations (last _N_ frames).  
2. **Configurable parameters**—all key constants (grid size, initial populations, energy costs, regrowth times, Perlin‐noise settings, etc.) can be adjusted via a Tkinter “Configuration” window before launching.  
3. **Perlin‐noise terrain** for realistic rock clusters (noise threshold & scale adjustable).  
4. **Energy labels** displayed on each agent (white text).  
5. **CSV population log** (`pop_log.csv`) recording time‐step, herbivore count, predator count, and grass count.  

---

## 🔧 Installation

This project uses [Poetry](https://python-poetry.org/) to manage dependencies.  
Make sure you have Python 3.13 installed (macOS ARM64 is supported). Then:

```bash
# 1. Clone or download this repo
git clone https://github.com/<your‐username>/ecosim‐mvp.git
cd ecosim‐mvp

# 2. Install dependencies via Poetry
poetry install
