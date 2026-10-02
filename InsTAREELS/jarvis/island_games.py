"""Five local games. No model calls, desktop input, task queues or network access."""
import random
from PIL import Image, ImageDraw
from .island import font

GAMES = ('Flappy', 'Snake', '2048', 'Tic Tac Toe', 'Memory')
HELP = {'Flappy': 'Click / Space to flap. Avoid the pillars.',
        'Snake': 'Arrow keys or WASD. Eat the purple stars.',
        '2048': 'Arrow keys or WASD. Merge tiles to reach 2048.',
        'Tic Tac Toe': 'Click a square. You are X; Jarvis plays O.',
        'Memory': 'Click two cards. Match all six pairs.'}


def merge(line):
    values = [x for x in line if x]
    result, score, i = [], 0, 0
    while i < len(values):
        if i + 1 < len(values) and values[i] == values[i+1]:
            result.append(values[i]*2)
            score += values[i]*2
            i += 2
        else:
            result.append(values[i])
            i += 1
    return result + [0]*(len(line)-len(result)), score


def winner(board):
    for a, b, c in ((0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)):
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return 'Draw' if all(board) else ''


def best_move(board):
    """Small exact minimax: the island opponent never blocks on inference."""
    def score(turn):
        outcome = winner(board)
        if outcome:
            return {'O': 1, 'X': -1, 'Draw': 0}[outcome]
        scores = []
        for i, cell in enumerate(board):
            if not cell:
                board[i] = turn
                scores.append(score('X' if turn == 'O' else 'O'))
                board[i] = ''
        return (max if turn == 'O' else min)(scores)
    ranked = []
    for i, cell in enumerate(board):
        if not cell:
            board[i] = 'O'
            ranked.append((score('X'), i))
            board[i] = ''
    return max(ranked)[1] if ranked else None


class Game:
    def __init__(self, name='Flappy', rng=None):
        if name not in GAMES:
            raise ValueError('Unknown island game')
        self.name, self.rng = name, rng or random.Random()
        self.reset()

    def reset(self):
        self.score = 0
        self.elapsed = 0.
        self.over = self.paused = self.started = False
        self.outcome = ''
        self.bird, self.velocity = 140., 0.
        self.pipes = [[440., self.rng.randint(90,190), False]]
        self.snake = [(7,7),(6,7),(5,7)]
        self.direction = self.next_direction = (1,0)
        self.food = self._food()
        self.grid = [[0]*4 for _ in range(4)]
        self._spawn(); self._spawn()
        self.board = ['']*9
        self.cards = list(range(6))*2
        self.rng.shuffle(self.cards)
        self.opened, self.matched = [], set()
        self.flip_wait = 0.

    def _food(self):
        free = [(x,y) for x in range(20) for y in range(12) if (x,y) not in self.snake]
        return self.rng.choice(free) if free else None

    def _spawn(self):
        free = [(y,x) for y in range(4) for x in range(4) if not self.grid[y][x]]
        if free:
            y,x = self.rng.choice(free)
            self.grid[y][x] = 2 if self.rng.random() < .9 else 4

    def key(self, key):
        if self.over or self.paused:
            return
        if self.name == 'Flappy' and key in ('space','Up','w'):
            self.started, self.velocity = True, -205.
        moves = {'Up':(0,-1),'Down':(0,1),'Left':(-1,0),'Right':(1,0),
                 'w':(0,-1),'s':(0,1),'a':(-1,0),'d':(1,0)}
        if key not in moves:
            return
        dx,dy = moves[key]
        self.started = True
        if self.name == 'Snake':
            if (dx,dy) != (-self.direction[0],-self.direction[1]):
                self.next_direction = (dx,dy)
        elif self.name == '2048':
            before = [row[:] for row in self.grid]
            for i in range(4):
                coords = [(i,x) for x in range(4)] if dx else [(y,i) for y in range(4)]
                if dx > 0 or dy > 0:
                    coords.reverse()
                line, earned = merge([self.grid[y][x] for y,x in coords])
                self.score += earned
                for (y,x), value in zip(coords,line):
                    self.grid[y][x] = value
            if before != self.grid:
                self._spawn()
            if any(2048 in row for row in self.grid):
                self.over, self.outcome = True, '2048! You won'
            elif not any(0 in row for row in self.grid) and not any(
                    self.grid[y][x] == self.grid[ny][nx] for y in range(4) for x in range(4)
                    for ny,nx in ((y+1,x),(y,x+1)) if ny<4 and nx<4):
                self.over, self.outcome = True, 'No moves left'

    def click(self, x, y):
        """Input in the renderer's 480 by 280 logical coordinates."""
        if self.over or self.paused:
            return
        if self.name == 'Flappy':
            self.key('space')
        elif self.name in {'Tic Tac Toe','Memory'}:
            cols, rows = (3,3) if self.name == 'Tic Tac Toe' else (4,3)
            if not (100 <= x < 380 and 20 <= y < 260):
                return
            index = int((y-20)//(240/rows))*cols + int((x-100)//(280/cols))
            self.started = True
            if self.name == 'Tic Tac Toe' and not self.board[index]:
                self.board[index] = 'X'
                result = winner(self.board)
                if not result:
                    self.board[best_move(self.board)] = 'O'
                    result = winner(self.board)
                if result:
                    self.over = True
                    self.outcome = 'Draw' if result == 'Draw' else result + ' wins'
            elif self.name == 'Memory' and len(self.opened)<2 and index not in self.matched and index not in self.opened:
                self.opened.append(index)
                if len(self.opened)==2:
                    self.score += 1
                    if self.cards[self.opened[0]] == self.cards[self.opened[1]]:
                        self.matched.update(self.opened)
                        self.opened = []
                        if len(self.matched)==12:
                            self.over, self.outcome = True, 'All pairs found!'
                    else:
                        self.flip_wait = .8

    def tick(self, dt):
        if self.paused or self.over or not self.started:
            return
        dt = min(.05, max(0., dt))  # No catch-up bursts after UI stalls.
        if self.name == 'Memory' and self.flip_wait:
            self.flip_wait = max(0., self.flip_wait-dt)
            if not self.flip_wait:
                self.opened = []
        elif self.name == 'Flappy':
            self.velocity += 560*dt
            self.bird += self.velocity*dt
            for pipe in self.pipes:
                pipe[0] -= 110*dt
                if pipe[0]+40 < 95 and not pipe[2]:
                    pipe[2] = True
                    self.score += 1
                if pipe[0]-10 < 95 < pipe[0]+50 and not pipe[1]-58 < self.bird < pipe[1]+58:
                    self.over = True
            if self.pipes[-1][0] < 275:
                self.pipes.append([480., self.rng.randint(80,200), False])
            self.pipes = [p for p in self.pipes if p[0]>-50]
            if not 10 < self.bird < 270:
                self.over = True
            if self.over:
                self.outcome = 'Flight complete'
        elif self.name == 'Snake':
            self.elapsed += dt
            if self.elapsed < .14:
                return
            self.elapsed = 0.
            self.direction = self.next_direction
            head = (self.snake[0][0]+self.direction[0], self.snake[0][1]+self.direction[1])
            eating = head == self.food
            if not (0<=head[0]<20 and 0<=head[1]<12) or head in (self.snake if eating else self.snake[:-1]):
                self.over, self.outcome = True, 'Snake stopped'
                return
            self.snake.insert(0,head)
            if eating:
                self.score += 1
                self.food = self._food()
                if self.food is None:
                    self.over, self.outcome = True, 'Board cleared!'
            else:
                self.snake.pop()

    def render(self):
        image = Image.new('RGB',(480,280),'#141827')
        draw = ImageDraw.Draw(image)
        def tile(box, fill, value=''):
            draw.rounded_rectangle(box,10,fill=fill)
            if value:
                draw.text(((box[0]+box[2])/2,(box[1]+box[3])/2), str(value),anchor='mm',font=font(26,True),fill='#faf8ff')
        if self.name == 'Flappy':
            for x,gap,_ in self.pipes:
                tile((x,-12,x+40,gap-70),'#6556a0')
                tile((x,gap+70,x+40,292),'#6556a0')
            draw.ellipse((85,self.bird-10,105,self.bird+10),fill='#f2cf80')
            draw.ellipse((97,self.bird-5,100,self.bird-2),fill='#141827')
        elif self.name == 'Snake':
            for x,y in self.snake:
                tile((40+x*20,20+y*20,58+x*20,38+y*20),'#8bdda8')
            if self.food:
                x,y = self.food
                draw.ellipse((43+x*20,23+y*20,55+x*20,35+y*20),fill='#c2adff')
        elif self.name == '2048':
            colors = {0:'#25293a',2:'#595170',4:'#746485',8:'#9b6685',16:'#af7663',32:'#bd945b',64:'#b4a154'}
            for y,row in enumerate(self.grid):
                for x,value in enumerate(row):
                    tile((112+x*64,12+y*64,172+x*64,72+y*64),colors.get(value,'#8062bd'),value or '')
        else:
            cols = 3 if self.name=='Tic Tac Toe' else 4
            for i in range(cols*3):
                x,y = 100+(i%cols)*280/cols,20+(i//cols)*80
                value = self.board[i] if cols==3 else str(self.cards[i]+1) if i in self.opened or i in self.matched else '·'
                color = '#415d55' if cols==4 and i in self.matched else '#302c49'
                tile((x+3,y+3,x+280/cols-3,y+77),color,value)
        draw.text((12,8),str(self.score),font=font(16,True),fill='#c2adff')
        caption = 'Paused' if self.paused else self.outcome if self.over else 'Click / Space to start' if self.name=='Flappy' and not self.started else ''
        if caption:
            draw.rounded_rectangle((70,110,410,164),15,fill='#08080a')
            draw.text((240,136),caption,font=font(19,True),fill='#eeeef4',anchor='mm')
        return image
