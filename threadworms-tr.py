# -*- coding: utf-8 -*-
#! python3

# Threadworms (bir Python/Pygame threading demosu)
# By Al Sweigart al@inventwithpython.com
# http://inventwithpython.com/blog
# "Basitleştirilmiş BSD" lisansı altında yayınlanmıştır
# (Bu koda ait İngilizce açıklamalar Ahmet Aksoy ahmetaksoy@gurmezin.com
# tarafından Türkçeleştirilmiştir. Kodlarda bir değişiklik yapılmamıştır.)

# Bu, öğretme amaçlı bir çoklu kullanım programlama anlamına gelmektedir,
# bu yüzden açıklamalara ağırlık verdim

import random, pygame, sys, threading
from pygame.locals import *

# Setting up constants
NUM_WORMS = 24  # ızgaradaki solucan sayısı 24
FPS = 30        # programın çalıştırdığı saniye başına çerçeve sayısı
CELL_SIZE = 20  # ızgaradaki hücrelerin pixel olarak eni ve yüksekliği
CELLS_WIDE = 32 # ızgaranın hücre sayısı olarak genişliği
CELLS_HIGH = 24 # ızgaranın hücre sayısı olarak yüksekliği


# Global ızgara veri yapısını oluştur. GRID[x][y] boş alan için None veya
# RGB üçlemesi içerir. Izgara, solucanların veri yazdığı paylaşılan ortak
# veri yapısıdır ve herbir solucan ayrı bir thread üzerinde çalıştığından
# solucanların diğerleriyle çakışmaması için kilit koymamız gerekir.
#
# Eğer thread kullanmasaydık, solucanların diğerleriyle çakışması mümkün
# olmazdı. Çünkü kodlar her zaman normal sırasıyla gerçekleşirdi. (Fakat
# o zaman da bizim programımız multithreaded olmazdı.)
GRID = []
for x in range(CELLS_WIDE):
    GRID.append([None] * CELLS_HIGH)

GRID_LOCKS = [] # çakışma istenmiyor
for x in range(CELLS_WIDE):
    column = []
    for y in range(CELLS_HIGH):
        column.append(threading.Lock()) # her bir hücre için bir Lock nesnesi oluştur
    GRID_LOCKS.append(column)

# Bazı renk sabitleri.
#             R    G    B
WHITE     = (255, 255, 255)
BLACK     = (  0,   0,   0)
DARKGRAY  = ( 40,  40,  40)
BGCOLOR = BLACK             # ızgaranın arkaplan rengi
GRID_LINES_COLOR = DARKGRAY # ızgara çizgilerinin rengi

# Tüm pencerenin pixel cinsinden enini ve yüksekliğini hesapla
WINDOWWIDTH = CELL_SIZE * CELLS_WIDE
WINDOWHEIGHT = CELL_SIZE * CELLS_HIGH

# Dört temel yön için sabit kullanıyoruz, çünkü DWON gibi hatalı bir yazım
# hemen bir NameError (isim hatası) verecek ve kolayca saptanacaktır.
# Oysa "dwon" biçiminde yanlış yazılmış bir string, Python kodlama
# açısından herhangi bir yazım hatası oluşturmayacak ve yakalanması güçleşecektir.
UP = 'up'
DOWN = 'down'
LEFT = 'left'
RIGHT = 'right'

# Bir solucanın vücut parçalarını tanımlayan veri yapısı "kafa"nın ilk eleman olduğu
# bir listedir. Bu yüzden HEAD'i indis olarak kullanabiliriz.

HEAD = 0

# Bilgisayar biliminde "kuyruk" genellikle en son eleman değil, kafadan
# sonra gelen *herbir" eleman için kullanılır. Bu yüzden solucan gövdesinin
# en son elemanını tarif etmek için "butt" (popo) sözcüğünü kullanacağım.

BUTT = -1 # negatif indisler sondan başlar, o yüzden -1 her zaman son indistir.

# Solucan threadlerinin var olup olmadığını kontrol etmek için global bir değişken
WORMS_RUNNING = True

class Worm(threading.Thread): # "Thread", "threading" modülündeki bir sınıftır.
    def __init__(self, name='Worm', maxsize=None, color=None, speed=200):
        # name (isim) hata denetimi (debugging) için kullanılabilir. Tetiklenen tüm istisnalarda
        # görünür. Böylece hangi thread'in çöktüğünü anlarsınız.
        # maxsize (max boyut)  solucanın (gövde segementi olarak) uzunluğudur.
        # color (renk) solucan rengini belirten RGB demetidir (tuple).
        # Daha koyu gölgeler otomatik olarak hesaplanır.
        # speed (hız) solucanın hareketten önceki milisaniye olarak bekleme süresidir.
        # 1000= saniyede bir, 0= olabildiğince hızlı anlamına gelir.

        threading.Thread.__init__(self) # Thread sınıfına override uyguladığımız için, ilk önce onun __init__() metodunu çağırmalıyız.
        self.name = name

        # maxsize'ı parametreye veya rasgele bir boyuta göre ayarla.
        if maxsize is None:
            self.maxsize = random.randint(4, 10)

            # Süper uzun bir solucan için küçük bir şans.
            if random.randint(0,4) == 0:
                self.maxsize += random.randint(10, 20)
        else:
            self.maxsize = maxsize

        # Rengi parametreye göre veya rasgele bir renge ayarla.
        if color is None:
            self.color = (random.randint(60, 255), random.randint(60, 255), random.randint(60, 255))
        else:
            self.color = color

        # Hızı parametreye göre veya rasgele bir sayıya ayarla.
        if speed is None:
            self.speed = random.randint(20, 500) # hareketten önce bekleme süresi 0.02 ila 0.5 saniye arasında olacak
        else:
            self.speed = speed

        # Gövde rasgele bir yerde (boş olduğundan emin ol) tek bir parça (segment) olarak başlar.
        # Solucan hareket etmeye başladığında, tam uzunluğuna erişene kadar yeni parçalar eklenir.
        while True:
            startx = random.randint(0, CELLS_WIDE - 1)
            starty = random.randint(0, CELLS_HIGH - 1)
            # Bu thread GRID_LOCKS kilidi serbest kalana kadar bekler
            # (eğer o sırada bir başka thread tarafından kullanılıyorsa). Bir başka thread
            # kilidi açmak isterse, acquire() komutu diğer thread kilidi serbest bırakana
            # kadar yanıt vermez (yani bloke olur).
            # (Kilidin boşalmasını bekleyen threadler bir kuyruk oluşturabilir) ve çalışmak
            # için önce seçilmeleri gerekir. Bu durumda onlar release() çağrısını yapana
            # kadar beklemek zorunda kalırız.)
            GRID_LOCKS[startx][starty].acquire() # bu thread kilidin açılmasını talep edene kadar bloke et
            if GRID[startx][starty] is None:
                break # ızgarada kullanılmayan bir hücre bulduk

        GRID[startx][starty] = self.color # paylaşılan veri yapısını değiştir

        # Şimdi tüm threadlerin paylaştığı veri yapısını (yani GRID'i) düzenlemeyi
        # tamamladık ve artık diğer threadlerin talep edebilmesi için (acquire)
        # kilidi serbest bırakabiliriz.
        GRID_LOCKS[startx][starty].release()

        # Solucanın gövdesi tek bir parça olarak başlar, tam uzunluğuna erişene
        # kadar uzar. Bu durum kurguyu (setup) kolaylaştırır.
        self.body = [{'x': startx, 'y': starty}]
        self.direction = random.choice((UP, DOWN, LEFT, RIGHT))

    def run(self):
        # Note that this thread's code only updates GRID, which is the variable
        # that tracks which cells have worm body segments and which are free.
        # Nothing in this thread draws pixels to the screen. So we could have this
        # code run separate from the visualization of the worms entirely!
        #
        # This means that instead of the Pygame grid display, we could write
        # code that displays the worms in 3D without changing the Worm class's
        # code at all. The visualization code just has to read the GRID variable
        # (in a thread-safe manner by using GRID_LOCKS, of course).
        while True:
            if not WORMS_RUNNING:
                return # run() döndüğünde bir iş parçacığı son bulur.

            # Yön değişimine rasgele karar ver
            if random.randint(0, 100) < 20: # 20% to change direction
                self.direction = random.choice((UP, DOWN, LEFT, RIGHT))

            nextx, nexty = self.getNextPosition()

            # GRID üzerinde değişiklik yapacağız, o yüzden ilk önce kilit işlemini
            # uygulamamız gerekir.
            origx, origy = nextx, nexty
            if origx not in (-1, CELLS_WIDE) and origy not in (-1, CELLS_HIGH):
                gotLock = GRID_LOCKS[origx][origy].acquire(timeout=1) # don't return (that is, block) until this thread can acquire the lock
                if not gotLock:
                    continue

            # Aslında nextx <0 veya nextx >= CELLS_WIDE kontrolünü yapmamız gerekir,
            # fakat solucanler her seferinde sadece tek bir adım gidebildiği için
            # sadece -1 veya CELLS_WIDE/CELLS_HIGH konumunda olup olmadıklarını
            # kontrol etmek yeterli olur.
            if nextx in (-1, CELLS_WIDE) or nexty in (-1, CELLS_HIGH) or GRID[nextx][nexty] is not None:
                # Solucanın ileri hareket alanı dolu, bu yüzden yeni bir yön bulmak gerekiyor.
                self.direction = self.getNewDirection()

                if self.direction is None:
                    # Gidecek yer yok, bu yüzden solucanı ters yöne çevirmeyi dene.
                    self.body.reverse() # Şimdi baş kuyruk, kuyruk baş oldu. Sihirbazlık!
                    self.direction = self.getNewDirection()

                if self.direction is not None:
                    # Bazı yönlere hareket mümkün, o yüzden yeni bir pozisyon iste.
                    nextx, nexty = self.getNextPosition()
            if origx not in (-1, CELLS_WIDE) and origy not in (-1, CELLS_HIGH):
                GRID_LOCKS[origx][origy].release()

            if self.direction is not None:
                GRID_LOCKS[nextx][nexty].acquire()
                # Izgara (grid) üzerinde boş yer var, o yüzden oraya git.
                GRID[nextx][nexty] = self.color # GRID durumunu yenile
                GRID_LOCKS[nextx][nexty].release()
                self.body.insert(0, {'x': nextx, 'y': nexty}) # bu solucanın kendi durumunu değiştir

                # Kuyruk çok uzamış mı diye kontrol et. Öyleyse kes.
                # Bu, solucan hareket ediyormuş gibi etki yaratır.

                # TODO - Burası "bug"ımız olan yer. Bazen solucanlar uzamaya devam eder ve üstüste binerler. Bu, onların threadlerini geciktirir.
                if len(self.body) > self.maxsize:
                    # TODO - Burada garip bir şeyler oluyor. Sepukku rutini temiz bir şekilde sonlandırmayı sağlıyor, fakat solucan hala ekranda görünüyor.
                    gotLock = GRID_LOCKS[self.body[BUTT]['x']][self.body[BUTT]['y']].acquire(timeout=2)
                    if not gotLock:
                        self.maxsize -= 1 # Bunun framerate'i niçin geliştirdiğinden tam emin değilim.
                        #print('chop %s' % (self.name))
                    GRID[self.body[BUTT]['x']][self.body[BUTT]['y']] = None # GRID durumunu değiştir
                    GRID_LOCKS[self.body[BUTT]['x']][self.body[BUTT]['y']].release()
                    del self.body[BUTT] # bu solucanın kendi durumunu değiştir (heh heh, worm butt)
            else:
                self.direction = random.choice((UP, DOWN, LEFT, RIGHT)) # hareket edemiyor, bu yüzden sadece rasgele bir yön seç

            # Teknik olarak bir solucan kafası (head) ve poposu (butt) aşağıdaki duruma
            # gelirse kendi içine sıkışır:
            #
            # Satır olarak:    "A" kafa ve "L" popodur:
            #    /\/\              CBKJ
            #    |HB|              DALI
            #    \--/              EFGH
            #
            # Bu durumu bir solucan düğümü olarak adlandırıyorum. bilgisayarımı
            # hıza 0 vererek gece boyunca açık bıraktım, fakat bir solucan düğümü
            # oluştuğunu görmedim, bu yüzden bu olasılığın çok düşük olduğunu varsayıyorum.

            # Pygame's pygame.time.wait() and the Python Standard Library's
            # time.time() functions (and the tick() method) are smart enough
            # to tell the operating system to put the thread to sleep for a
            # while and just run other threads instead. Of course, while the
            # OS could interrupt our thread at any time to hand execution off
            # to a different thread, calling wait() or sleep() is a way we can
            # explicitly say, "Go ahead and don't run this thread for X
            # milliseconds."
            #
            # This wouldn't happen if we have "wait" code like this:
            # startOfWait = time.time()
            # while time.time() - 5 > startOfWait:
            #     pass # do nothing for 5 seconds
            #
            # The above code also implements "waiting", but to the OS it looks
            # like your thread is still executing code (even though this code
            # is doing nothing but looping until 5 seconds has passed).
            # This is inefficient, because time spent executing the above pointless
            # loop is time that could have been spent executing other thread's
            # code.
            # Of course, if ALL worms' threads are sleeping, then the computer
            # can know it can use the CPU to run other programs besides
            # our Python Threadworms script.
            pygame.time.wait(self.speed)

            # The beauty of using multiple threads here is that we can have
            # the worms move at different rates of speed just by passing a
            # different integer to wait().
            # If we did this program in a single thread, we would have to
            # calculate how often we update the position of each worm based
            # on their speed relative to all the other worms, which would
            # be a headache. But now we have the threads doing this work
            # for us!


    def getNextPosition(self):
        # Figure out the x and y of where the worm's head would be next, based
        # on the current position of its "head" and direction member.

        if self.direction == UP:
            nextx = self.body[HEAD]['x']
            nexty = self.body[HEAD]['y'] - 1
        elif self.direction == DOWN:
            nextx = self.body[HEAD]['x']
            nexty = self.body[HEAD]['y'] + 1
        elif self.direction == LEFT:
            nextx = self.body[HEAD]['x'] - 1
            nexty = self.body[HEAD]['y']
        elif self.direction == RIGHT:
            nextx = self.body[HEAD]['x'] + 1
            nexty = self.body[HEAD]['y']
        else:
            assert False, 'self.direction için yanlış değer: %s' % self.direction

        # Remember that nextx & nexty could be invalid (by referring to a location
        # on the grid already taken by a body segment or beyond the boundaries
        # of the window.)
        return nextx, nexty


    def getNewDirection(self):
        x = self.body[HEAD]['x'] # sentetik şeker aşağıdaki kodları daha okunur yapar
        y = self.body[HEAD]['y']

        # Solucanın gidebileceği olası yönlerin listesini oluştur.
        newDirection = []
        if y - 1 not in (-1, CELLS_HIGH) and GRID[x][y - 1] is None:
            newDirection.append(UP)
        if y + 1 not in (-1, CELLS_HIGH) and GRID[x][y + 1] is None:
            newDirection.append(DOWN)
        if x - 1 not in (-1, CELLS_WIDE) and GRID[x - 1][y] is None:
            newDirection.append(LEFT)
        if x + 1 not in (-1, CELLS_WIDE) and GRID[x + 1][y] is None:
            newDirection.append(RIGHT)

        if newDirection == []:
            return None # Solucan için gidecek olası yer kalmadığında None döndürülür.

        return random.choice(newDirection)

def main():
    global FPSCLOCK, DISPLAYSURF

    # Izgara üzerinde bazı duvarlar çiz
    squares = """
...........................
...........................
...........................
.H..H..EEE..L....L.....OO..
.H..H..E....L....L....O..O.
.HHHH..EE...L....L....O..O.
.H..H..E....L....L....O..O.
.H..H..EEE..LLL..LLL...OO..
...........................
.W.....W...OO...RRR..MM.MM.
.W.....W..O..O..R.R..M.M.M.
.W..W..W..O..O..RR...M.M.M.
.W..W..W..O..O..R.R..M...M.
..WW.WW....OO...R.R..M...M.
...........................
...........................
"""
    #setGridSquares(squares)

    # Pygame penceresi kuruldu.
    pygame.init()
    FPSCLOCK = pygame.time.Clock()
    DISPLAYSURF = pygame.display.set_mode((WINDOWWIDTH, WINDOWHEIGHT))
    pygame.display.set_caption('Threadworms')

    # Solucan nesnelerini yarat.
    worms = [] # tüm solucan nesnelerini içeren liste
    for i in range(NUM_WORMS):
        worms.append(Worm(name='Worm %s' % i))
        worms[-1].start() # Solucan kodunu kendi iş parçacığında başlat.

    DISPLAYSURF.fill(BGCOLOR)
    while True: # ana oyun döngüsü
        handleEvents()
        drawGrid()

        pygame.display.update()
        FPSCLOCK.tick(FPS)


def handleEvents():
    # Bu programda ele almamız gereken tek olay, bitiştir.
    global WORMS_RUNNING

    for event in pygame.event.get(): # olay ele alma döngüsü
        if (event.type == QUIT) or (event.type == KEYDOWN and event.key == K_ESCAPE):
            WORMS_RUNNING = False # False yapılması solucan iş parçacığını sonlandırma anlamı taşır.
            pygame.quit()
            sys.exit()


def drawGrid():
    # Izgara çizgilerini çiz.
    for x in range(0, WINDOWWIDTH, CELL_SIZE): # düşey satırları sil
        pygame.draw.line(DISPLAYSURF, GRID_LINES_COLOR, (x, 0), (x, WINDOWHEIGHT))
    for y in range(0, WINDOWHEIGHT, CELL_SIZE): # yatay satırları sil
        pygame.draw.line(DISPLAYSURF, GRID_LINES_COLOR, (0, y), (WINDOWWIDTH, y))

    # Ana döngüdeki (drawGrid'i çağıran) ana thread, GRID değişkenini değiştirmeden önce
    # GRID_LOCKS tesisine gerek duyar.

    for x in range(0, CELLS_WIDE):
        for y in range(0, CELLS_HIGH):
            gotLock = GRID_LOCKS[x][y].acquire(timeout=0.02)
            if not gotLock:
                # Eğer bu hücre için kilit koyamıyorsak, hiçbir şeyi silme ve olduğu gibi bırak.
                continue

            if GRID[x][y] is None:
                # Bu hücrede çizilecek body segment yok, bu yüzden boş bir kare çiz
                pygame.draw.rect(DISPLAYSURF, BGCOLOR, (x * CELL_SIZE + 1, y * CELL_SIZE + 1, CELL_SIZE - 1, CELL_SIZE - 1))
                GRID_LOCKS[x][y].release() # GRID'i okumayı bitirdi, bu yüzden kilidi serbest bırak.
            else:
                color = GRID[x][y] # GRID veri yapısını oku
                GRID_LOCKS[x][y].release() # GRIDle işimiz bitti, kilidi serbest bırakabiliriz.

                # Ekranda body segmentini çiz
                darkerColor = (max(color[0] - 50, 0), max(color[1] - 50, 0), max(color[2] - 50, 0))
                pygame.draw.rect(DISPLAYSURF, darkerColor, (x * CELL_SIZE,     y * CELL_SIZE,     CELL_SIZE,     CELL_SIZE    ))
                pygame.draw.rect(DISPLAYSURF, color,       (x * CELL_SIZE + 4, y * CELL_SIZE + 4, CELL_SIZE - 8, CELL_SIZE - 8))


def setGridSquares(squares, color=(192, 192, 192)):
    # "squares", "değişim yok" için '.', boş hücre için ' ' ve diğerleri
    # renkli boşluk içeren çok satırlı bir stringdir.
    # Girişi kolaylaştırmak için konan en baş ve sondaki boş satırlar
    # ihmal edilmektedir.
    #
    # squares aşağıdaki gibi bir değere sahiptir:
    # """
    # ......
    # ...XX.
    # ...XX.
    # ......
    # """

    squares = squares.split('\n')
    if squares[0] == '':
        del squares[0]
    if squares[-1] == '':
        del squares[-1]

    for y in range(min(len(squares), CELLS_HIGH)):
        for x in range(min(len(squares[y]), CELLS_WIDE)):
            GRID_LOCKS[x][y].acquire()
            if squares[y][x] == ' ':
                GRID[x][y] = None
            elif squares[y][x] == '.':
                pass
            else:
                GRID[x][y] = color
            GRID_LOCKS[x][y].release()

if __name__ == '__main__':
    main()