"""
ecosim_mvp.py
Ecosystem simulation with grass, herbivores, and predators.
Version 0.8 — full, executable file with energy labels drawn for both species.

Controls
--------
[Space]  pause / resume  |  [Esc]  quit

Colour key
----------
Green = grass Blue = herbivore Red = predator White digits = current energy
"""

import pygame, random, noise
import csv, time
import matplotlib.pyplot as plt
from collections import defaultdict
from collections import deque
from matplotlib.animation import FuncAnimation

# ---------------- GLOBAL CONSTANTS ---------------- #
GRID_W, GRID_H = 120, 60          # grid dimensions (tiles)
TILE           = 10              # pixel size of a tile
FPS            = 8

ROCK_THRESH = 0.15                # smaller = more rocks
ROCK_SCALE = 10.0                 # bigger = larger rock blobs

NUM_HERB = 50                    # initial herbivores
NUM_PRED = 10                     # initial predators

FOOD_REGROW   = 30               # turns for eaten grass to regrow

# Herbivore energetics
H_INIT        = 10
H_MOVE_COST   = 1
H_BASAL_COST  = 0
H_FOOD_GAIN   = 3
H_FOOD_WAIT   = 1
H_REPRO_COST  = 5
H_REPRO_TH    = 25

# Predator energetics
P_INIT        = 30
P_MOVE_COST   = 1
P_BASAL_COST  = 0
P_FOOD_GAIN   = 10
P_FOOD_WAIT   = 2
P_REPRO_COST  = 10
P_REPRO_TH    = 70

# Colours (R,G,B)
COL_BG = (230, 255, 200) # (30, 30, 30)
COL_ROCK  = (120, 120, 120)
COL_FOOD = (150, 250, 150) # (0, 160, 0)
COL_HERB = (70, 160, 255)
COL_PRED = (200, 60, 60)
COL_TEXT = (255, 255, 255)

DIRS = [(0,-1),(1,0),(0,1),(-1,0)]   # N,E,S,W
wrap = lambda v, size: v % size      # toroidal helper

# Max # of frames for the chart
MAX_WIN = 1000
    
# ---------------- WORLD (Grass grid) ---------------- #
class FoodGrid:
    def __init__(self, w, h, rocks):
        self.w, self.h, self.rocks = w, h, rocks
        self.food  = [[True for _ in range(w)] for _ in range(h)]
        self.timer = [[0    for _ in range(w)] for _ in range(h)]
        
        for (x,y) in rocks:
            self.food[y][x]  = False     # no grass
            self.timer[y][x] = None      # never regrows

    # basic queries
    def has(self, x, y):
        return self.food[y][x]

    def eat(self, x, y):
        self.food [y][x] = False
        self.timer[y][x] = FOOD_REGROW

    # ---- new helper: at least one 4-neighbour tile still has food ----
    def _has_food_neighbour(self, x, y):
        for dx, dy in DIRS: # N,E,S,W
            nx, ny = wrap(x + dx, self.w), wrap(y + dy, self.h)
            if self.food[ny][nx]:
                return True
        return False

    # update each turn
    def update(self):
        to_regrow = [] # tiles that will regrow this tick

        # 1) scan, count down timers, decide who *could* regrow
        for y in range(self.h):
            for x in range(self.w):
                if not self.food[y][x] and self.timer[y][x] != None:
                    if self._has_food_neighbour(x, y):   # uses the *old* grid
                        self.timer[y][x] -= 1
                        if self.timer[y][x] <= 0:
                            to_regrow.append((x, y))

        # 2) apply regrowth in one shot (doesn't affect other checks this tick)
        for x, y in to_regrow:
            self.food[y][x]  = True
            self.timer[y][x] = 0

# ---------------- HERBIVORE ---------------- #
class Herbivore:
    def __init__(self, x, y, dir_idx):
        self.x, self.y = x, y
        self.facing    = dir_idx
        self.energy    = H_INIT
        self.intended  = (x, y)
        self.wait = 0
    # ---- behaviour ----
    def decide(self, grass, occupied, rocks):
        dx,dy = DIRS[self.facing]
        ahead = (wrap(self.x+dx, GRID_W), wrap(self.y+dy, GRID_H))
        if grass.has(*ahead):
            self.intended = ahead; return
        opts = []
        for idx,(ox,oy) in enumerate(DIRS):
            nx,ny = wrap(self.x+ox, GRID_W), wrap(self.y+oy, GRID_H)
            if (nx,ny) not in occupied and (nx,ny) not in rocks:
                opts.append((nx,ny,idx))
        if opts:
            nx,ny,ndir = random.choice(opts)
            self.intended=(nx,ny); self.facing=ndir
        else:
            self.intended=(self.x,self.y)
    def move(self):
        if self.wait:
            self.wait -= 1
            return
        self.x, self.y = self.intended
    # ---- physiology ----
    def forage(self, grass):
        if grass.has(self.x,self.y):
            grass.eat(self.x,self.y)
            self.energy += H_FOOD_GAIN
            self.wait = H_FOOD_WAIT
    def hunger(self):
        if self.wait:                # digesting → pay basal cost only
            self.energy -= H_BASAL_COST
        else:                        # moved or at least tried to
            self.energy -= H_MOVE_COST
        return self.energy <= 0
    def pos(self):
        return (self.x,self.y)

# ---------------- PREDATOR ---------------- #
class Predator:
    def __init__(self,x,y):
        self.x,self.y = x,y
        self.energy   = P_INIT
        self.intended = (x,y)
        self.wait = 0
    def _dist(self,a,b,size):
        d = abs(a-b)
        return min(d, size-d)
    # ---- behaviour ----
    def decide(self, herb_positions, occupied, rocks):
        if not herb_positions:
            opts = [(wrap(self.x+ox, GRID_W), wrap(self.y+oy, GRID_H))
                    for ox, oy in DIRS
                    if (wrap(self.x+ox, GRID_W), wrap(self.y+oy, GRID_H)) not in occupied
                       and (wrap(self.x+ox, GRID_W), wrap(self.y+oy, GRID_H)) not in rocks]  # rock check
            self.intended = random.choice(opts) if opts else (self.x, self.y)
            return
        target = min(herb_positions,key=lambda p:self._dist(p[0],self.x,GRID_W)+self._dist(p[1],self.y,GRID_H))
        tx,ty=target; steps=[]
        if self.x!=tx:
            dx=1 if (tx-self.x)%GRID_W < (self.x-tx)%GRID_W else -1
            steps.append((wrap(self.x+dx,GRID_W), self.y))
        if self.y!=ty:
            dy=1 if (ty-self.y)%GRID_H < (self.y-ty)%GRID_H else -1
            steps.append((self.x, wrap(self.y+dy,GRID_H)))
        random.shuffle(steps)
        for nx,ny in steps:
            if (nx,ny) not in occupied and (nx,ny) not in rocks:
                self.intended=(nx,ny); break
        else:
            self.intended=(self.x,self.y)
    def move(self):
        if self.wait:
            self.wait -= 1
            return
        self.x,self.y=self.intended
    # ---- physiology ----
    def eat(self, herb_dict):
        if herb_dict.pop((self.x,self.y),None):
            self.energy += P_FOOD_GAIN
            self.wait = P_FOOD_WAIT
    def hunger(self):
        if self.wait:                # digesting → pay basal cost only
            self.energy -= P_BASAL_COST
        else:                        # moved or at least tried to
            self.energy -= P_MOVE_COST
        return self.energy <= 0
    def pos(self):
        return (self.x,self.y)

# ---------------- MAIN LOOP ---------------- #

def draw_energy(screen, font, value, x, y):
    txt = font.render(str(value), True, COL_TEXT)
    rect = txt.get_rect(center=(x*TILE+TILE//2, y*TILE+TILE//2))
    screen.blit(txt, rect)

def main():
    # ----- set up Matplotlib live plot -----
    plt.ion()
    fig, ax1 = plt.subplots()
    ax1.set_xlabel("frame")
    ax1.set_ylabel("predator")

    ax2 = ax1.twinx()                         # second y-axis on the right
    ax2.set_ylabel("prey")

    # line handles
    ln_pred, = ax1.plot([], [], color="red",   label="predator")
    ln_herb, = ax2.plot([], [], color="blue",  label="prey")

    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")

    t_hist      = deque(maxlen=MAX_WIN)
    herb_hist   = deque(maxlen=MAX_WIN)
    pred_hist   = deque(maxlen=MAX_WIN)

    def update_plot(frame):
        if t_hist:
            ax1.set_xlim(t_hist[0], t_hist[-1])
        ln_herb.set_data(t_hist, herb_hist)
        ln_pred.set_data(t_hist, pred_hist)
        ax1.relim(); ax1.autoscale_view()
        ax2.relim(); ax2.autoscale_view()
        return ln_herb, ln_pred

    anim = FuncAnimation(fig, update_plot, interval=200)  # 5 fps for chart
    # ----- end matplotlib setup -----

    log = open("pop_log.csv", "w", newline="")
    writer = csv.writer(log)
    writer.writerow(["time", "herb", "pred", "grass"])
    t = 0

    pygame.init(); pygame.font.init()
    font = pygame.font.SysFont(None, 12)
    screen = pygame.display.set_mode((GRID_W*TILE, GRID_H*TILE))
    pygame.display.set_caption("Ecosim -- Mr. Huang")
    clock = pygame.time.Clock()

    # generate rocks and grass
    seed = int(time.time()) & 0xFF      # keep base 0-255
    rocks = {
        (x, y)
        for y in range(GRID_H)
        for x in range(GRID_W)
        if noise.pnoise2(
               x / ROCK_SCALE, y / ROCK_SCALE,
               octaves     = 4,
               persistence = 0.5,
               lacunarity  = 2.0,
               repeatx     = GRID_W,
               repeaty     = GRID_H,
               base        = seed
           ) > ROCK_THRESH
    }
    grass = FoodGrid(GRID_W, GRID_H, rocks)
    
    # make sure initial creatures don’t spawn on a rock
    herb=[Herbivore(*pos, random.randrange(4))
          for pos in set((random.randrange(GRID_W), random.randrange(GRID_H))
                         for _ in range(NUM_HERB)) - rocks]
    pred=[Predator(*pos)
          for pos in set((random.randrange(GRID_W), random.randrange(GRID_H))
                         for _ in range(NUM_PRED)) - rocks]

    paused=False; running=True
    while running:
        # ---------- events ----------
        for e in pygame.event.get():
            if e.type==pygame.QUIT: running=False
            elif e.type==pygame.KEYDOWN:
                if e.key==pygame.K_SPACE: paused=not paused
                elif e.key==pygame.K_ESCAPE: running=False
        if paused:
            clock.tick(FPS); continue
        else:
            t += 1

        # ===== PREDATOR PHASE =====
        herb_dict={h.pos():h for h in herb}
        occ_pred={p.pos() for p in pred}
        herb_positions=list(herb_dict.keys())
        for p in pred: p.decide(herb_positions, occ_pred, rocks)
        moveP=defaultdict(list)
        for p in pred: moveP[p.intended].append(p)
                
        # --- resolve moves & leave babies on the vacated tiles ---
        new_pred = []
        occ_pred_after = set()
        for pack in moveP.values():
            mover = random.choice(pack)
            old_pos = mover.pos()
            mover.move()
            occ_pred_after.add(mover.pos())

            if mover.energy >= P_REPRO_TH and old_pos not in occ_pred_after:
                mover.energy -= P_REPRO_COST + P_INIT
                new_pred.append(Predator(old_pos[0], old_pos[1]))

        # ---- eat on the new tile ----
        for p in pred:
            p.eat(herb_dict)

        # ---- add offspring ----
        pred.extend(new_pred)

        # ---- hunger & remove starved ----
        pred = [p for p in pred if not p.hunger()]
        
        herb=list(herb_dict.values())

        # ===== HERBIVORE PHASE =====
        occ_start={h.pos() for h in herb}
        for h in herb: h.decide(grass, occ_start, rocks)
        destH=defaultdict(list)
        for h in herb: destH[h.intended].append(h)
        new_herb=[]; occ_after=set()
        for group in destH.values():
            mover = random.choice(group)
            old   = mover.pos()
            mover.move()
            occ_after.add(mover.pos())
            # reproduce on vacated tile if enough energy and tile free
            if mover.energy >= H_REPRO_TH and old not in occ_after:
                mover.energy -= H_REPRO_COST + H_INIT
                new_herb.append(Herbivore(old[0], old[1], random.randrange(4)))

        # foraging & hunger
        for h in herb:
            h.forage(grass)
        herb = [h for h in herb if not h.hunger()] + new_herb

        # ===== ENVIRONMENT UPDATE =====
        grass.update()
        
        # ===== MATPLOTLIB UPDATE =====
        t_hist.append(t)
        herb_hist.append(len(herb))
        pred_hist.append(len(pred))
        plt.pause(0.001)                  # let matplotlib process GUI events
        
        # log to csv
        writer.writerow([t, len(herb), len(pred), sum(sum(row) for row in grass.food)])

        # ===== RENDER =====
        screen.fill(COL_BG)
        for y in range(GRID_H):
            for x in range(GRID_W):
                if grass.has(x, y):
                    pygame.draw.rect(screen, COL_FOOD, (x*TILE, y*TILE, TILE, TILE))
                    
        for x,y in rocks:
            pygame.draw.rect(screen, COL_ROCK, (x*TILE, y*TILE, TILE, TILE))

        for h in herb:
            pygame.draw.rect(screen, COL_HERB, (h.x*TILE, h.y*TILE, TILE, TILE))
            draw_energy(screen, font, h.energy, h.x, h.y)
        for p in pred:
            pygame.draw.rect(screen, COL_PRED, (p.x*TILE, p.y*TILE, TILE, TILE))
            draw_energy(screen, font, p.energy, p.x, p.y)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    log.close()

if __name__ == "__main__":
    main()
