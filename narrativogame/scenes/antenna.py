import math
import random
import pygame

from settings import WIDTH, HEIGHT
from engine.scene_manager import Scene
from scenes.pipes import PipesScene
from game.antenna_logic import calcular_probabilidad, cae_rayo


class AntennaScene(Scene):
    """
    MINIJUEGO 4 - La tormenta del bosque (juego de Nicol).

    Cómo se juega (también se explica dentro del juego, tecla H = ayuda):
        PASO 1  Explorar el bosque y juntar fragmentos (esquivar los bichos).
        PASO 2  Ir a la cabaña de Luna y hablar con ella (tecla E).
        PASO 3  En el mapa, elegir 3 zonas para poner pararrayos. Cada zona
                tiene un % = probabilidad de capturar un rayo.
        PASO 4  Cae la tormenta: 5 rayos (cada uno cae en uno de tus pararrayos
                elegido al azar y se captura con el % de esa zona) y al final un
                RAYO GIGANTE: hay que refugiarse para no perder fragmentos.

    Resultado:
        exito   : 4 rayos capturados y 4 fragmentos
        parcial : 2 rayos capturados y 2 fragmentos
        fallo   : cualquier otro caso

    Fases: bosque, dialogo, mapa, tormenta, gran_rayo, resultado
    """

    TOTAL_RAYOS = 5
    TOTAL_FRAGMENTOS = 5
    INTERVALO_RAYO = 2.0        # segundos entre rayos
    GRAN_RAYO_EN = 12.0         # segundos desde que empieza la tormenta
    DURACION_GRAN_RAYO = 4.0    # segundos para refugiarse
    RAYOS_EXITO = 4
    FRAGMENTOS_EXITO = 4
    RAYOS_PARCIAL = 2
    FRAGMENTOS_PARCIAL = 2

    # Textos de ayuda: clave -> (título, párrafos)
    AYUDAS = {
        "intro": (
            "¿CÓMO SE JUEGA?",
            [
                "Se viene una tormenta eléctrica. ¡Protegé el bosque con pararrayos!",
                "PASO 1: Caminá con WASD o las flechas y juntá los fragmentos azules. "
                "Los bichos violetas te los roban: esquivalos.",
                "PASO 2: Andá a la cabaña de Luna y apretá E para hablar con ella.",
                "PASO 3: En el mapa elegí 3 zonas para los pararrayos. Cada zona muestra "
                "su % de chance de capturar un rayo.",
                "PASO 4: Caen 5 rayos y después un RAYO GIGANTE: corré al refugio o a la "
                "cabaña para no perder fragmentos.",
                "Ganás con 4 rayos capturados y 4 fragmentos. Apretá H cuando quieras "
                "volver a ver la ayuda.",
            ],
        ),
        "mapa": (
            "PASO 3: ELEGÍ DÓNDE PONER LOS PARARRAYOS",
            [
                "Cada cuadro es una zona del bosque. El número grande es la probabilidad "
                "de capturar un rayo ahí.",
                "Los colores van del azul (poco probable) al rojo (muy probable). Esa "
                "probabilidad depende de la altura del árbol (lo que más pesa), la energía, "
                "la actividad eléctrica y la cercanía a la tormenta.",
                "Cada rayo va a caer en uno de tus pararrayos, elegido al azar, y se "
                "captura con el % de esa zona.",
                "Abajo ves el promedio de tu elección y cuántos rayos esperás capturar. "
                "¡Necesitás 4 de 5!",
                "Hacé clic en una zona para poner o quitar un pararrayos. Con 3 colocados, "
                "apretá ESPACIO.",
            ],
        ),
        "tormenta": (
            "PASO 4: ¡EMPEZÓ LA TORMENTA!",
            [
                "Van a caer 5 rayos, uno cada 2 segundos. Los pararrayos trabajan solos: "
                "vos no tenés que hacer nada con ellos.",
                "Mientras tanto, juntá los fragmentos que te falten y esquivá los bichos "
                "eléctricos (si te tocan, te roban uno).",
                "Arriba a la derecha ves los rayos: verde = capturado, rojo = se escapó.",
                "Cuando terminen los 5 rayos, cae un RAYO GIGANTE. ¡Andá cerca del refugio "
                "o de la cabaña!",
            ],
        ),
        "gran_rayo": (
            "¡RAYO GIGANTE!",
            [
                "¡Corré al REFUGIO o a la CABAÑA (marcados en verde)! Tenés 4 segundos.",
                "Si te agarra al aire libre, perdés hasta 3 fragmentos.",
            ],
        ),
    }

    def __init__(self, manager, state, audio):
        super().__init__(manager)

        self.state = state
        self.audio = audio

        self.font_title = pygame.font.Font(None, 48)
        self.font = pygame.font.Font(None, 28)
        self.font_med = pygame.font.Font(None, 26)
        self.font_small = pygame.font.Font(None, 22)
        self.font_mini = pygame.font.Font(None, 19)

        self.ayudas_vistas = set()
        self.reiniciar(mostrar_intro=True)

    # ---------------------------------------------------------
    # INICIO
    # ---------------------------------------------------------

    def reiniciar(self, mostrar_intro=False):
        self.fase = "bosque"
        self.input_cooldown = 0.5
        self.ayuda_clave = None
        if mostrar_intro:
            self.ayuda_clave = "intro"
            self.ayudas_vistas.add("intro")

        # Personaje (posición con decimales para que el movimiento sea suave)
        self.player = pygame.Rect(90, HEIGHT - 150, 32, 45)
        self.px, self.py = float(self.player.x), float(self.player.y)
        self.speed = 230
        self.invulnerable = 0.0

        # Cabaña y refugio (zonas seguras)
        self.cabana = pygame.Rect(WIDTH - 180, 150, 130, 110)
        self.refugio = pygame.Rect(70, 170, 110, 85)

        # Fragmentos (todos dentro de la pantalla)
        self.fragmentos = [
            pygame.Rect(300, 400, 18, 18),
            pygame.Rect(500, 270, 18, 18),
            pygame.Rect(700, 430, 18, 18),
            pygame.Rect(560, 460, 18, 18),
            pygame.Rect(825, 470, 18, 18),
        ]
        self.fragmentos_recolectados = 0
        self.fragmentos_perdidos = 0

        # Árboles (la altura se muestra en metros, igual que en el mapa)
        self.arboles = [
            {"rect": pygame.Rect(250, 120, 50, 130), "altura": 8, "quemado": False},
            {"rect": pygame.Rect(420, 350, 55, 150), "altura": 13, "quemado": True},
            {"rect": pygame.Rect(610, 120, 60, 180), "altura": 16, "quemado": True},
            {"rect": pygame.Rect(760, 340, 50, 120), "altura": 7, "quemado": False},
            {"rect": pygame.Rect(870, 320, 65, 195), "altura": 18, "quemado": True},
        ]

        # Bichos eléctricos (más lentos que el jugador)
        self.bichos = [
            {"x": 400.0, "y": 200.0, "rect": pygame.Rect(400, 200, 24, 24), "espera": 0.0},
            {"x": 640.0, "y": 380.0, "rect": pygame.Rect(640, 380, 24, 24), "espera": 0.0},
        ]

        # Zonas del mapa de la cabaña
        self.zonas = [
            {"nombre": "Zona norte", "rect": pygame.Rect(170, 180, 145, 110),
             "altura": 0.70, "energia": 0.45, "actividad": 0.40, "cercania": 0.60},
            {"nombre": "Zona quemada", "rect": pygame.Rect(335, 180, 145, 110),
             "altura": 0.88, "energia": 0.85, "actividad": 0.90, "cercania": 0.80},
            {"nombre": "Zona central", "rect": pygame.Rect(500, 180, 145, 110),
             "altura": 0.95, "energia": 0.72, "actividad": 0.75, "cercania": 0.90},
            {"nombre": "Zona del lago", "rect": pygame.Rect(665, 180, 145, 110),
             "altura": 0.55, "energia": 0.35, "actividad": 0.30, "cercania": 0.45},
            {"nombre": "Zona sur", "rect": pygame.Rect(335, 330, 145, 110),
             "altura": 0.78, "energia": 0.60, "actividad": 0.65, "cercania": 0.55},
        ]
        for zona in self.zonas:
            zona["probabilidad"] = calcular_probabilidad(
                zona["altura"], zona["energia"], zona["actividad"], zona["cercania"]
            )

        self.pararrayos = []
        self.max_pararrayos = 3
        self.zona_hover = None

        self.mensaje = "Juntá fragmentos y encontrá la cabaña de Luna."
        self.color_mensaje = (255, 235, 150)
        self.dialogo_lineas = [
            "Luna: ¡Llegaste justo a tiempo!",
            "Luna: La tormenta se está cargando demasiado rápido.",
            "Luna: Vamos a instalar tres pararrayos para atrapar los rayos.",
            "Luna: En el mapa, cada zona tiene un porcentaje: es la chance de capturar un rayo ahí.",
            "Luna: Rojo es más chance; azul, menos. Depende de la altura del árbol, la energía, la actividad y la cercanía.",
            "Luna: Después juntá los fragmentos que falten y buscá refugio cuando caiga el rayo gigante.",
        ]
        self.dialogo_indice = 0

        self.tiempo_tormenta = 0.0
        self.tiempo_rayo = 0.0
        self.tiempo_gran = 0.0
        self.rayos_totales = 0
        self.rayos_capturados = 0
        self.rayos_hist = []          # True = capturado, False = se escapó
        self.p_promedio = 0.0         # chance promedio de la elección del jugador
        self.protegido_gran_rayo = None

        self.temblor = 0
        self.destello = 0.0
        self.color_destello = (255, 255, 255)
        self.resultado = ""

    def cambiar_fase(self, fase):
        self.fase = fase
        if fase in self.AYUDAS and fase not in self.ayudas_vistas:
            self.ayudas_vistas.add(fase)
            self.ayuda_clave = fase
            self.input_cooldown = 0.25

    def clave_ayuda_actual(self):
        if self.fase in ("bosque", "dialogo"):
            return "intro"
        if self.fase in self.AYUDAS:
            return self.fase
        return None

    # ---------------------------------------------------------
    # UTILIDADES
    # ---------------------------------------------------------

    def texto(self, superficie, contenido, posicion, fuente=None, color=(240, 240, 240), centro=False):
        fuente = fuente or self.font
        imagen = fuente.render(contenido, True, color)

        if centro:
            rect = imagen.get_rect(center=posicion)
        else:
            rect = imagen.get_rect(topleft=posicion)

        superficie.blit(imagen, rect)
        return rect

    def texto_ajustado(self, superficie, contenido, posicion, color, ancho_max=WIDTH - 40):
        """Texto centrado de una sola línea: achica la letra si no entra en pantalla."""
        fuente = self.font_small
        if fuente.size(contenido)[0] > ancho_max:
            fuente = self.font_mini
        return self.texto(superficie, contenido, posicion, fuente, color, True)

    def parrafo(self, superficie, contenido, y, fuente, color, ancho=800, interlineado=4, x=None):
        """Texto centrado que se corta en varias líneas si no entra. Devuelve la próxima y."""
        x = WIDTH // 2 if x is None else x
        linea, lineas = "", []
        for palabra in contenido.split():
            prueba = (linea + " " + palabra).strip()
            if fuente.size(prueba)[0] > ancho and linea:
                lineas.append(linea)
                linea = palabra
            else:
                linea = prueba
        if linea:
            lineas.append(linea)
        alto = fuente.get_height()
        for l in lineas:
            self.texto(superficie, l, (x, y + alto // 2), fuente, color, True)
            y += alto + interlineado
        return y

    def esta_cerca(self, rect_a, rect_b, distancia=70):
        return rect_a.inflate(distancia, distancia).colliderect(rect_b)

    def color_probabilidad(self, probabilidad):
        if probabilidad < 0.35:
            return (70, 130, 220)
        if probabilidad < 0.55:
            return (80, 190, 130)
        if probabilidad < 0.70:
            return (235, 205, 70)
        if probabilidad < 0.82:
            return (240, 140, 55)
        return (225, 65, 65)

    def zona_segura(self):
        return (
            self.player.colliderect(self.cabana)
            or self.player.colliderect(self.refugio)
        )

    def prob_al_menos(self, p, n, k):
        """P(capturar al menos k de n rayos) si cada rayo se captura con prob. p."""
        return sum(
            math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(k, n + 1)
        )

    def promedio_elegido(self):
        if not self.pararrayos:
            return 0.0
        return sum(z["probabilidad"] for z in self.pararrayos) / len(self.pararrayos)

    def sonido_click(self):
        if self.audio:
            try:
                self.audio.play_click()
            except Exception:
                pass

    # ---------------------------------------------------------
    # EVENTOS
    # ---------------------------------------------------------

    def handle_event(self, event):
        if self.input_cooldown > 0:
            return

        # Ventana de ayuda: pausa el juego hasta cerrarla
        if self.ayuda_clave:
            cierra = (
                event.type == pygame.KEYDOWN
                and event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_h)
            ) or (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1)
            if cierra:
                self.ayuda_clave = None
                self.input_cooldown = 0.15
            return

        if event.type == pygame.KEYDOWN:
            # H: abrir la ayuda de la etapa actual
            if event.key == pygame.K_h and self.clave_ayuda_actual():
                self.ayuda_clave = self.clave_ayuda_actual()
                self.input_cooldown = 0.15
                return

            if self.fase == "bosque":
                if event.key == pygame.K_e:
                    if self.esta_cerca(self.player, self.cabana):
                        self.cambiar_fase("dialogo")
                        self.mensaje = "Hablá con Luna."
                    else:
                        self.mensaje = "Acercate a la cabaña y volvé a apretar E."
                        self.color_mensaje = (255, 235, 150)

            elif self.fase == "dialogo":
                if event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_e):
                    self.dialogo_indice += 1

                    if self.dialogo_indice >= len(self.dialogo_lineas):
                        self.mensaje = "Elegí tres zonas para colocar los pararrayos."
                        self.cambiar_fase("mapa")

            elif self.fase == "mapa":
                if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    if len(self.pararrayos) == self.max_pararrayos:
                        self.p_promedio = self.promedio_elegido()
                        self.mensaje = "¡Volvé al bosque y juntá los fragmentos que faltan!"
                        self.color_mensaje = (255, 235, 150)
                        self.cambiar_fase("tormenta")
                    else:
                        self.mensaje = (
                            f"Tenés que colocar los tres pararrayos "
                            f"(llevás {len(self.pararrayos)})."
                        )

            elif self.fase == "resultado":
                if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.manager.replace(
                        PipesScene(self.manager, self.state, self.audio)
                    )
                elif event.key == pygame.K_r and self.resultado != "exito":
                    self.reiniciar(mostrar_intro=False)

        if event.type == pygame.MOUSEMOTION and self.fase == "mapa":
            self.zona_hover = None
            for zona in self.zonas:
                if zona["rect"].collidepoint(event.pos):
                    self.zona_hover = zona

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.fase == "mapa":
                self.seleccionar_zona(event.pos)

    def seleccionar_zona(self, posicion):
        for zona in self.zonas:
            if zona["rect"].collidepoint(posicion):
                self.sonido_click()
                if zona in self.pararrayos:
                    self.pararrayos.remove(zona)
                    self.mensaje = "Pararrayos retirado."
                    return

                if len(self.pararrayos) < self.max_pararrayos:
                    self.pararrayos.append(zona)
                    self.mensaje = (
                        f"Pararrayos colocado en {zona['nombre']} "
                        f"({zona['probabilidad'] * 100:.0f} %)"
                    )
                else:
                    self.mensaje = "Ya colocaste los tres. Quitá uno (clic) para cambiarlo."

    # ---------------------------------------------------------
    # ACTUALIZACIÓN
    # ---------------------------------------------------------

    def update(self, dt):
        if self.input_cooldown > 0:
            self.input_cooldown -= dt

        if self.ayuda_clave:
            return   # ayuda abierta: el juego espera

        if self.invulnerable > 0:
            self.invulnerable -= dt
        if self.destello > 0:
            self.destello -= dt

        if self.fase in ("bosque", "tormenta", "gran_rayo"):
            self.mover_jugador(dt)

        if self.fase == "bosque":
            self.recolectar_fragmentos()
            self.mover_bichos(dt)

        elif self.fase == "tormenta":
            self.actualizar_tormenta(dt)
            self.recolectar_fragmentos()
            self.mover_bichos(dt)

        elif self.fase == "gran_rayo":
            self.actualizar_gran_rayo(dt)

    def mover_jugador(self, dt):
        teclas = pygame.key.get_pressed()
        dx = 0
        dy = 0

        if teclas[pygame.K_a] or teclas[pygame.K_LEFT]:
            dx -= 1
        if teclas[pygame.K_d] or teclas[pygame.K_RIGHT]:
            dx += 1
        if teclas[pygame.K_w] or teclas[pygame.K_UP]:
            dy -= 1
        if teclas[pygame.K_s] or teclas[pygame.K_DOWN]:
            dy += 1

        if dx != 0 or dy != 0:
            largo = math.hypot(dx, dy)          # en diagonal no va más rápido
            self.px += dx / largo * self.speed * dt
            self.py += dy / largo * self.speed * dt

        self.px = max(20, min(WIDTH - self.player.width - 20, self.px))
        self.py = max(110, min(HEIGHT - self.player.height - 20, self.py))
        self.player.x = int(self.px)
        self.player.y = int(self.py)

    def recolectar_fragmentos(self):
        for fragmento in self.fragmentos[:]:
            if self.player.colliderect(fragmento):
                self.fragmentos.remove(fragmento)
                self.fragmentos_recolectados += 1
                self.mensaje = (
                    f"Fragmento recogido: "
                    f"{self.fragmentos_recolectados}/{self.TOTAL_FRAGMENTOS}"
                )
                self.color_mensaje = (150, 240, 255)

    def mover_bichos(self, dt):
        segura = self.zona_segura()
        for bicho in self.bichos:
            if bicho["espera"] > 0:
                bicho["espera"] -= dt
                sentido = -1          # recién robó: se aleja
            else:
                sentido = 1

            if not segura or sentido == -1:
                vx = self.player.centerx - bicho["x"]
                vy = self.player.centery - bicho["y"]
                dist = math.hypot(vx, vy) or 1.0
                velocidad = 60 * dt * sentido
                bicho["x"] += vx / dist * velocidad
                bicho["y"] += vy / dist * velocidad

            bicho["x"] = max(20, min(WIDTH - 44, bicho["x"]))
            bicho["y"] = max(110, min(HEIGHT - 44, bicho["y"]))
            bicho["rect"].x = int(bicho["x"])
            bicho["rect"].y = int(bicho["y"])

            if (
                bicho["rect"].colliderect(self.player)
                and self.invulnerable <= 0
                and not segura
                and bicho["espera"] <= 0
            ):
                if self.fragmentos_recolectados > 0:
                    self.fragmentos_recolectados -= 1
                    self.fragmentos_perdidos += 1
                    self.mensaje = "¡Un bicho eléctrico te robó un fragmento!"
                    self.color_mensaje = (240, 120, 120)
                    bicho["espera"] = 3.0
                    self.invulnerable = 1.5

    def actualizar_tormenta(self, dt):
        self.tiempo_tormenta += dt
        self.tiempo_rayo += dt

        if self.tiempo_rayo >= self.INTERVALO_RAYO and self.rayos_totales < self.TOTAL_RAYOS:
            self.tiempo_rayo = 0
            self.rayos_totales += 1

            zona = random.choice(self.pararrayos)
            capturado = cae_rayo(zona["probabilidad"])
            self.rayos_hist.append(capturado)

            if capturado:
                self.rayos_capturados += 1
                self.mensaje = (
                    f"Rayo {self.rayos_totales}/{self.TOTAL_RAYOS}: cayó en "
                    f"{zona['nombre']} ({zona['probabilidad'] * 100:.0f} %) - ¡CAPTURADO!"
                )
                self.color_mensaje = (110, 240, 150)
                self.color_destello = (110, 240, 150)
            else:
                self.mensaje = (
                    f"Rayo {self.rayos_totales}/{self.TOTAL_RAYOS}: cayó en "
                    f"{zona['nombre']} ({zona['probabilidad'] * 100:.0f} %) - se escapó."
                )
                self.color_mensaje = (240, 120, 120)
                self.color_destello = (240, 120, 120)
            self.destello = 0.4

        if self.rayos_totales >= self.TOTAL_RAYOS and self.tiempo_tormenta >= self.GRAN_RAYO_EN:
            self.tiempo_gran = 0.0
            self.mensaje = "¡RAYO GIGANTE! ¡Buscá refugio!"
            self.color_mensaje = (255, 150, 90)
            self.cambiar_fase("gran_rayo")

    def actualizar_gran_rayo(self, dt):
        self.tiempo_gran += dt
        self.temblor = int(5 + self.tiempo_gran * 3)

        if self.tiempo_gran >= self.DURACION_GRAN_RAYO:
            self.protegido_gran_rayo = self.zona_segura()

            if self.protegido_gran_rayo:
                self.mensaje = "¡Te refugiaste a tiempo y conservaste tus fragmentos!"
            else:
                perdidos = min(3, self.fragmentos_recolectados)
                self.fragmentos_recolectados -= perdidos
                self.fragmentos_perdidos += perdidos
                self.mensaje = (
                    f"El gran rayo te hizo perder {perdidos} fragmentos."
                )

            self.calcular_resultado()
            self.cambiar_fase("resultado")

    def calcular_resultado(self):
        if (
            self.rayos_capturados >= self.RAYOS_EXITO
            and self.fragmentos_recolectados >= self.FRAGMENTOS_EXITO
        ):
            self.resultado = "exito"
            if not self.state.flags.get("antena_superada"):
                self.state.add("bondad", 1)       # el premio se da una sola vez
            self.state.set_flag("antena_superada", True)

        elif (
            self.rayos_capturados >= self.RAYOS_PARCIAL
            and self.fragmentos_recolectados >= self.FRAGMENTOS_PARCIAL
        ):
            self.resultado = "parcial"
            self.state.set_flag("antena_parcial", True)

        else:
            self.resultado = "fallo"
            self.state.set_flag("antena_superada", False)

    # ---------------------------------------------------------
    # DIBUJO
    # ---------------------------------------------------------

    def draw(self):
        superficie = self.manager.screen

        if self.fase in ("bosque", "tormenta", "gran_rayo", "resultado"):
            self.dibujar_bosque(superficie)

        elif self.fase in ("dialogo", "mapa"):
            self.dibujar_cabana(superficie)

        if self.fase == "dialogo":
            self.dibujar_dialogo(superficie)

        elif self.fase == "mapa":
            self.dibujar_mapa(superficie)

        elif self.fase == "resultado":
            self.dibujar_resultado(superficie)

        if self.ayuda_clave:
            self.dibujar_ayuda(superficie)

    # ---- ayuda ----

    def dibujar_ayuda(self, superficie):
        capa = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        capa.fill((0, 0, 0, 215))
        superficie.blit(capa, (0, 0))

        titulo, parrafos = self.AYUDAS[self.ayuda_clave]
        self.texto(superficie, titulo, (WIDTH // 2, 55), self.font_title, (255, 230, 140), True)

        y = 100
        for p in parrafos:
            y = self.parrafo(superficie, p, y, self.font_med, (235, 235, 235), ancho=820, interlineado=3) + 10

        self.texto(
            superficie,
            "ESPACIO o clic para seguir",
            (WIDTH // 2, HEIGHT - 35),
            self.font,
            (255, 230, 120),
            True,
        )

    # ---- bosque / tormenta ----

    def texto_paso(self):
        if self.fase == "bosque":
            return "PASOS 1 y 2: juntá los fragmentos azules y andá a la cabaña de Luna (tecla E)."
        if self.fase == "tormenta":
            return "PASO 4: ¡la tormenta! Juntá los fragmentos que falten y esquivá los bichos."
        if self.fase == "gran_rayo":
            return "¡RAYO GIGANTE! Corré al REFUGIO o a la CABAÑA (cuadros verdes)."
        return "Resultado de la tormenta."

    def dibujar_bosque(self, superficie):
        superficie.fill((30, 75, 65))

        # Cielo y lluvia
        pygame.draw.rect(superficie, (35, 45, 75), (0, 0, WIDTH, 100))

        for x in range(0, WIDTH, 55):
            pygame.draw.line(
                superficie,
                (150, 190, 220),
                (x, 105),
                (x - 15, HEIGHT),
                1,
            )

        # Árboles
        for arbol in self.arboles:
            rect = arbol["rect"]

            color_tronco = (75, 45, 30) if not arbol["quemado"] else (45, 38, 35)
            color_copa = (35, 150, 70) if not arbol["quemado"] else (60, 60, 60)

            pygame.draw.rect(
                superficie,
                color_tronco,
                (rect.centerx - 9, rect.centery, 18, rect.height // 2),
            )

            pygame.draw.circle(
                superficie,
                color_copa,
                (rect.centerx, rect.y + 35),
                35,
            )

            if arbol["quemado"]:
                self.texto(
                    superficie,
                    "X",
                    (rect.centerx, rect.y + 35),
                    self.font,
                    (240, 90, 60),
                    True,
                )

            self.texto(
                superficie,
                f"{arbol['altura']} m",
                (rect.centerx, rect.y + 80),
                self.font_small,
                (225, 235, 225),
                True,
            )

        # Cabaña
        pygame.draw.rect(superficie, (125, 75, 45), self.cabana)
        techo = [
            (self.cabana.left - 15, self.cabana.top),
            (self.cabana.centerx, self.cabana.top - 60),
            (self.cabana.right + 15, self.cabana.top),
        ]
        pygame.draw.polygon(superficie, (90, 40, 40), techo)
        pygame.draw.rect(
            superficie,
            (50, 30, 25),
            (self.cabana.centerx - 18, self.cabana.bottom - 55, 36, 55),
        )
        self.texto(
            superficie,
            "CABAÑA",
            (self.cabana.centerx, self.cabana.bottom + 18),
            self.font_small,
            (255, 235, 150),
            True,
        )

        # Refugio exterior
        pygame.draw.rect(superficie, (100, 70, 45), self.refugio)
        pygame.draw.polygon(
            superficie,
            (75, 45, 35),
            [
                (self.refugio.left - 10, self.refugio.top),
                (self.refugio.centerx, self.refugio.top - 35),
                (self.refugio.right + 10, self.refugio.top),
            ],
        )
        self.texto(
            superficie,
            "REFUGIO",
            self.refugio.center,
            self.font_small,
            (255, 235, 160),
            True,
        )

        # Zonas seguras resaltadas durante la tormenta
        if self.fase in ("tormenta", "gran_rayo"):
            urgente = self.fase == "gran_rayo"
            grosor = 5 if urgente else 3
            for rect in (self.cabana, self.refugio):
                pygame.draw.rect(superficie, (110, 240, 150), rect.inflate(16, 16), grosor, border_radius=8)
                self.texto(
                    superficie,
                    "SEGURO",
                    (rect.centerx, rect.bottom + (40 if rect is self.cabana else 16)),
                    self.font_small,
                    (110, 240, 150),
                    True,
                )

        # Fragmentos
        for fragmento in self.fragmentos:
            pygame.draw.circle(
                superficie,
                (80, 220, 255),
                fragmento.center,
                10,
            )
            pygame.draw.circle(
                superficie,
                (220, 255, 255),
                fragmento.center,
                4,
            )

        # Bichos
        for bicho in self.bichos:
            centro = bicho["rect"].center
            pygame.draw.circle(superficie, (190, 70, 240), centro, 12)
            pygame.draw.circle(superficie, (255, 230, 80), (centro[0] - 5, centro[1] - 3), 3)
            pygame.draw.circle(superficie, (255, 230, 80), (centro[0] + 5, centro[1] - 3), 3)

        # Personaje (parpadea un instante si un bicho le robó algo)
        if self.invulnerable <= 0 or int(self.invulnerable * 10) % 2 == 0:
            pygame.draw.rect(superficie, (60, 150, 240), self.player)
            pygame.draw.circle(
                superficie,
                (245, 190, 140),
                (self.player.centerx, self.player.top - 8),
                14,
            )

        # Cartel "E: hablar" cerca de la cabaña
        if self.fase == "bosque":
            cerca = self.esta_cerca(self.player, self.cabana)
            pygame.draw.rect(
                superficie,
                (255, 230, 120) if cerca else (200, 180, 100),
                self.cabana.inflate(24, 24),
                4 if cerca else 2,
                border_radius=8,
            )
            if cerca:
                self.texto(
                    superficie,
                    "Apretá E para hablar con Luna",
                    (self.cabana.centerx - 40, self.cabana.bottom + 46),
                    self.font,
                    (255, 240, 150),
                    True,
                )

        self.dibujar_hud(superficie)

        # Destello del resultado de cada rayo
        if self.destello > 0:
            capa = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            capa.fill((*self.color_destello, int(90 * min(1.0, self.destello / 0.4))))
            superficie.blit(capa, (0, 0))

        if self.fase in ("tormenta", "gran_rayo"):
            self.dibujar_relampago(superficie)

        if self.fase == "gran_rayo":
            restante = max(0.0, self.DURACION_GRAN_RAYO - self.tiempo_gran)
            color = (255, 90, 90) if self.zona_segura() is False else (110, 240, 150)
            texto = "¡EN SEGURO!" if self.zona_segura() else f"¡CORRÉ AL REFUGIO!  {restante:.1f}"
            self.texto(superficie, texto, (WIDTH // 2, 150), self.font_title, color, True)

        # Mensaje de abajo
        self.texto(
            superficie,
            self.mensaje,
            (WIDTH // 2, HEIGHT - 25),
            self.font if self.font.size(self.mensaje)[0] <= WIDTH - 30 else self.font_small,
            self.color_mensaje,
            True,
        )

    def dibujar_hud(self, superficie):
        self.texto(superficie, self.texto_paso(), (20, 10), self.font_small, (255, 230, 120))
        self.texto(
            superficie,
            "WASD o flechas: moverte  |  E: hablar  |  H: ayuda",
            (20, 34),
            self.font_small,
            (190, 200, 215),
        )
        self.texto(
            superficie,
            f"Fragmentos: {self.fragmentos_recolectados}/{self.TOTAL_FRAGMENTOS} "
            f"(necesitás {self.FRAGMENTOS_EXITO})  |  "
            f"Rayos: {self.rayos_capturados}/{self.TOTAL_RAYOS} "
            f"(necesitás {self.RAYOS_EXITO})",
            (20, 62),
            self.font_small,
            (150, 240, 255),
        )

        # Medidor de rayos (verde = capturado, rojo = se escapó, gris = pendiente)
        if self.fase in ("tormenta", "gran_rayo", "resultado"):
            x0 = WIDTH - 190
            self.texto(superficie, "Rayos", (x0 + 70, 14), self.font_small, (230, 230, 230), True)
            for i in range(self.TOTAL_RAYOS):
                centro = (x0 + 14 + i * 34, 40)
                if i < len(self.rayos_hist):
                    color = (110, 240, 150) if self.rayos_hist[i] else (240, 100, 100)
                    pygame.draw.circle(superficie, color, centro, 12)
                else:
                    pygame.draw.circle(superficie, (70, 78, 100), centro, 12)
                pygame.draw.circle(superficie, (210, 215, 230), centro, 12, 2)

            if self.fase == "tormenta":
                if self.rayos_totales < self.TOTAL_RAYOS:
                    falta = max(0.0, self.INTERVALO_RAYO - self.tiempo_rayo)
                    texto = f"Próximo rayo en {falta:.1f} s"
                else:
                    falta = max(0.0, self.GRAN_RAYO_EN - self.tiempo_tormenta)
                    texto = f"Rayo gigante en {falta:.1f} s"
                self.texto(superficie, texto, (x0 + 70, 76), self.font_small, (255, 190, 120), True)

    def dibujar_relampago(self, superficie):
        if self.rayos_totales > 0:
            x = random.randint(200, WIDTH - 200)
            pygame.draw.line(
                superficie,
                (255, 255, 230),
                (x, 100),
                (x - 30, 220),
                5,
            )
            pygame.draw.line(
                superficie,
                (255, 255, 230),
                (x - 30, 220),
                (x + 20, 310),
                5,
            )

        if self.fase == "gran_rayo":
            capa = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            capa.fill((255, 255, 255, 45))
            superficie.blit(capa, (random.randint(-self.temblor, self.temblor), 0))

    # ---- cabaña / diálogo ----

    def dibujar_cabana(self, superficie):
        superficie.fill((75, 52, 45))

        pygame.draw.rect(superficie, (115, 75, 45), (100, 80, WIDTH - 200, HEIGHT - 150))
        pygame.draw.rect(superficie, (45, 35, 30), (170, 160, 170, 130))
        pygame.draw.rect(superficie, (40, 30, 25), (WIDTH - 310, 150, 170, 150))

        self.texto(
            superficie,
            "CABAÑA DEL BOSQUE",
            (WIDTH // 2, 45),
            self.font_title,
            (255, 230, 150),
            True,
        )

        self.texto(
            superficie,
            "Luna, la guardabosques",
            (WIDTH // 2, HEIGHT - 55),
            self.font,
            (255, 235, 160),
            True,
        )

    def dibujar_dialogo(self, superficie):
        panel = pygame.Surface((WIDTH - 100, 180), pygame.SRCALPHA)
        panel.fill((15, 20, 35, 235))
        superficie.blit(panel, (50, HEIGHT - 220))

        if self.dialogo_indice < len(self.dialogo_lineas):
            linea = self.dialogo_lineas[self.dialogo_indice]
        else:
            linea = "Luna: Revisá el mapa y elegí tres zonas."

        self.parrafo(superficie, linea, HEIGHT - 195, self.font, (255, 255, 255), ancho=WIDTH - 160)

        self.texto(
            superficie,
            f"({self.dialogo_indice + 1}/{len(self.dialogo_lineas)})  ESPACIO o ENTER para continuar",
            (WIDTH // 2, HEIGHT - 60),
            self.font_small,
            (255, 230, 120),
            True,
        )

    # ---- mapa ----

    def dibujar_mapa(self, superficie):
        superficie.fill((30, 35, 50))

        self.texto(
            superficie,
            "MAPA DE ACTIVIDAD ELÉCTRICA",
            (WIDTH // 2, 32),
            self.font_title,
            (255, 230, 140),
            True,
        )

        self.texto(
            superficie,
            "Elegí 3 zonas para los pararrayos. El % es la chance de capturar un rayo ahí.",
            (WIDTH // 2, 70),
            self.font_small,
            (230, 230, 230),
            True,
        )

        # Leyenda de colores
        self.texto(superficie, "poco probable", (WIDTH // 2 - 160, 108), self.font_small, (150, 180, 240), True)
        for i, muestra in enumerate((0.2, 0.45, 0.6, 0.75, 0.9)):
            pygame.draw.rect(
                superficie,
                self.color_probabilidad(muestra),
                (WIDTH // 2 - 80 + i * 32, 99, 30, 18),
                border_radius=4,
            )
        self.texto(superficie, "muy probable", (WIDTH // 2 + 150, 108), self.font_small, (240, 140, 130), True)

        for zona in self.zonas:
            color = self.color_probabilidad(zona["probabilidad"])
            pygame.draw.rect(superficie, color, zona["rect"], border_radius=10)
            borde = (255, 255, 255) if zona is self.zona_hover else (240, 240, 240)
            pygame.draw.rect(superficie, borde, zona["rect"], 5 if zona is self.zona_hover else 3, border_radius=10)

            if zona in self.pararrayos:
                pygame.draw.circle(superficie, (255, 255, 255), zona["rect"].center, 28, 5)
                self.texto(
                    superficie,
                    "P",
                    zona["rect"].center,
                    self.font_title,
                    (255, 255, 255),
                    True,
                )

            altura_metros = int(zona["altura"] * 20)

            self.texto(
                superficie,
                zona["nombre"],
                (zona["rect"].centerx, zona["rect"].y + 18),
                self.font_small,
                (20, 25, 35),
                True,
            )

            self.texto(
                superficie,
                f"Árbol: {altura_metros} m",
                (zona["rect"].centerx, zona["rect"].y + 48),
                self.font_small,
                (20, 25, 35),
                True,
            )

            if zona not in self.pararrayos:
                self.texto(
                    superficie,
                    f"{zona['probabilidad'] * 100:.0f} %",
                    (zona["rect"].centerx, zona["rect"].y + 80),
                    self.font,
                    (20, 25, 35),
                    True,
                )

        # Detalle de la zona señalada con el mouse
        if self.zona_hover:
            z = self.zona_hover
            detalle = (
                f"{z['nombre']}: altura {z['altura'] * 100:.0f}% (x40) + "
                f"energía {z['energia'] * 100:.0f}% (x30) + actividad {z['actividad'] * 100:.0f}% (x20) + "
                f"cercanía {z['cercania'] * 100:.0f}% (x10) = {z['probabilidad'] * 100:.0f}%"
            )
            color_detalle = (230, 230, 240)
        else:
            detalle = "Pasá el mouse por una zona para ver de qué depende su porcentaje."
            color_detalle = (150, 158, 180)
        self.texto_ajustado(superficie, detalle, (WIDTH // 2, 468), color_detalle)

        self.texto(
            superficie,
            f"Pararrayos colocados: {len(self.pararrayos)}/{self.max_pararrayos}",
            (WIDTH // 2, 448),
            self.font,
            (150, 240, 255),
            True,
        )

        # Resumen de la elección
        if self.pararrayos:
            p = self.promedio_elegido()
            esperado = p * self.TOTAL_RAYOS
            chance_exito = self.prob_al_menos(p, self.TOTAL_RAYOS, self.RAYOS_EXITO)
            resumen = (
                f"Tu elección: {p * 100:.0f}% por rayo -> esperás capturar ~{esperado:.1f} de 5  |  "
                f"chance de 4 o más: {chance_exito * 100:.0f}%"
            )
            color_resumen = (255, 235, 150)
        else:
            resumen = "Todavía no elegiste ninguna zona."
            color_resumen = (150, 158, 180)
        self.texto_ajustado(superficie, resumen, (WIDTH // 2, 492), color_resumen)

        self.texto(
            superficie,
            "Clic: colocar o quitar un pararrayos  |  ESPACIO: confirmar (con 3)  |  H: ayuda",
            (WIDTH // 2, 144),
            self.font_small,
            (255, 230, 130),
            True,
        )

        self.texto(
            superficie,
            self.mensaje,
            (WIDTH // 2, 518),
            self.font_small,
            (255, 230, 130),
            True,
        )

    # ---- resultado ----

    def dibujar_resultado(self, superficie):
        capa = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        capa.fill((10, 15, 25, 238))
        superficie.blit(capa, (0, 0))

        if self.resultado == "exito":
            titulo = "¡BOSQUE PROTEGIDO!"
            color = (100, 240, 140)
            mensaje = "Los pararrayos funcionaron muy bien."
        elif self.resultado == "parcial":
            titulo = "PROTECCIÓN PARCIAL"
            color = (245, 210, 90)
            mensaje = "Algunas zonas quedaron protegidas."
        else:
            titulo = "LA TORMENTA GANÓ"
            color = (245, 100, 100)
            mensaje = "Los pararrayos no fueron suficientes."

        self.texto(superficie, titulo, (WIDTH // 2, 60), self.font_title, color, True)
        self.texto(superficie, mensaje, (WIDTH // 2, 100), self.font, (240, 240, 240), True)
        self.texto(superficie, self.mensaje, (WIDTH // 2, 132), self.font_small, (200, 210, 225), True)

        esperado = self.p_promedio * self.TOTAL_RAYOS
        ok_rayos = self.rayos_capturados >= self.RAYOS_EXITO
        ok_frag = self.fragmentos_recolectados >= self.FRAGMENTOS_EXITO

        y = 175
        self.texto(
            superficie,
            f"Rayos capturados: {self.rayos_capturados}/{self.TOTAL_RAYOS}   (esperabas ~{esperado:.1f})",
            (WIDTH // 2, y),
            self.font,
            (150, 230, 255),
            True,
        )
        self.texto(
            superficie,
            f"Fragmentos conservados: {self.fragmentos_recolectados}/{self.TOTAL_FRAGMENTOS}   "
            f"(perdidos: {self.fragmentos_perdidos})",
            (WIDTH // 2, y + 36),
            self.font,
            (150, 230, 255),
            True,
        )

        self.texto(superficie, "Para ganar necesitabas:", (WIDTH // 2, y + 86), self.font_small, (230, 230, 230), True)
        self.texto(
            superficie,
            f"{self.RAYOS_EXITO} rayos capturados: " + ("CUMPLIDO" if ok_rayos else "no llegaste"),
            (WIDTH // 2, y + 112),
            self.font_small,
            (110, 240, 150) if ok_rayos else (240, 120, 120),
            True,
        )
        self.texto(
            superficie,
            f"{self.FRAGMENTOS_EXITO} fragmentos: " + ("CUMPLIDO" if ok_frag else "no llegaste"),
            (WIDTH // 2, y + 136),
            self.font_small,
            (110, 240, 150) if ok_frag else (240, 120, 120),
            True,
        )

        y2 = self.parrafo(
            superficie,
            f"Lo que aprendiste: tus pararrayos tenían en promedio {self.p_promedio * 100:.0f}% de chance por rayo. "
            "Aun con buena probabilidad, el azar puede jugar en contra: por eso conviene elegir las zonas con "
            "mayor porcentaje.",
            y + 168,
            self.font_small,
            (255, 235, 150),
            ancho=800,
        )

        pie = "ESPACIO: continuar" if self.resultado == "exito" else "ESPACIO: continuar   |   R: reintentar"
        self.texto(superficie, pie, (WIDTH // 2, HEIGHT - 32), self.font, (255, 230, 120), True)
