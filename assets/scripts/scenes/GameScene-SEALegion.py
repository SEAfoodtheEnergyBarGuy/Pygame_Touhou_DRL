import numpy as np
import pygame
from pygame.locals import *
import json

from assets.scripts.classes.game_logic.BulletData import BulletData
from assets.scripts.classes.game_logic.Enemy import Enemy
from assets.scripts.classes.game_logic.Item import *
from assets.scripts.classes.game_logic.Player import Player
from assets.scripts.classes.hud_and_rendering.Scene import Scene, render_fps
from assets.scripts.classes.hud_and_rendering.SpriteSheet import SpriteSheet
from assets.scripts.math_and_data.Vector2 import Vector2
from assets.scripts.classes.game_logic.AttackFunctions import AttackFunctions

from assets.scripts.learning.rlAgent import agent
from assets.scripts.learning import mlData, plotter

from assets.scripts.math_and_data.enviroment import *

from PIL import Image


class GameScene(Scene):
    def __init__(self):
        super().__init__()
        self.GAME_ZONE = tuple(map(int, os.getenv("GAME_ZONE").split(', ')))
        self.delta_time = 0.001 #0.001

        music_module.play_music("08.-Voile_-the-Magic-Library_1.wav")

        self.background = Image.open(path_join("assets", "sprites", "backgrounds", "background.png")).convert("RGBA")
        self.background.paste(Image.new("RGBA", (GAME_ZONE[2], GAME_ZONE[3]), (255, 255, 255, 0)),
                              (GAME_ZONE[0], GAME_ZONE[1]))
        self.bg = pygame.sprite.Sprite()
        self.bg.rect = Rect(0, 0, WIDTH, HEIGHT)
        self.bg.image = pygame.image.fromstring(self.background.tobytes(), self.background.size, self.background.mode).convert_alpha()

        self.font = pygame.font.Font(path_join("assets", "fonts", "DFPPOPCorn-W12.ttf"), 36)

        self.player = Player(0, self, mlData.hp)
        self.agent = agent(self.player)

        self.enemy_bullets = []
        self.items = []
        self.bullet_cleaner = None

        self.effects = []

        self.bullet_group = pygame.sprite.RenderPlain()
        self.item_group = pygame.sprite.RenderPlain()
        self.hud_group = pygame.sprite.RenderPlain()
        self.entity_group = pygame.sprite.RenderPlain()
        self.effect_group = pygame.sprite.RenderPlain()

        self.time = 0
        self.level = json.load(open(path_join("assets", "levels", "level_1.json")))
        self.level_enemies = sorted(self.level["enemies"], key=lambda enemy: enemy["time"])
        self.enemy_count = 0

        self.enemies = []

        self.agent.terminal = False
        self.agent.time = self.time
        #self.agent.state = tuple(self.player.position.coords)
        self.agent.ring = Collider(mlData.proxyRange, self.player.position)

    def process_input(self, events):
        for evt in events:
            if evt.type == QUIT:
                pygame.quit()
        if self.agent.episode>mlData.epMax:
            pygame.quit()

        if  self.agent.initBool:
            self.agent.initBool = False
        else:
            self.agent.state=mlData.replay[-1][1]

        move_direction=self.agent.selectAction()
           
        self.player.move(move_direction)

        '''
        #True gamers don't slow down
        if pygame.key.get_pressed()[pygame.K_LSHIFT]:
            self.player.slow = True
        else:
            self.player.slow = False
        '''


    def update(self, delta_time):
        self.delta_time = delta_time
        self.time += delta_time
        self.agent.time = self.time
        self.agent.ring.update_position(self.player.position)

        if self.time >= self.level["length"]:
            mlData.terminal = True
            #self.player.switch_to_scoreboard()

        if self.level_enemies and self.enemy_count < len(self.level_enemies):
            if self.time >= self.level_enemies[self.enemy_count]["time"]:
                enemy_data = self.level_enemies[self.enemy_count]
                enemy = Enemy(
                    position=Vector2(GAME_ZONE[0], GAME_ZONE[1]) + Vector2(*enemy_data["start_position"]),
                    trajectory=list(map(np.array, [enemy_data["start_position"]]+ enemy_data["trajectory"])),
                    speed=enemy_data["speed"],
                    sprite_sheet=SpriteSheet(path_join(*enemy_data["sprite"]["path"])).crop(enemy_data["sprite"]["size"]),
                    collider=Collider(enemy_data["collider"]["radius"], offset=Vector2(*enemy_data["collider"]["offset"])),
                    hp=enemy_data["hp"],
                    attack_data=[(*attack[:3], (path_join(*attack[3][0]), attack[3][1], attack[3][2], attack[3][3], Vector2(*attack[3][4])), *attack[4:]) for attack in enemy_data["attacks"]],
                    drop=(enemy_data["drop"]["list"], enemy_data["drop"]["list"]),
                    clear_bullets_on_death=enemy_data["clear_on_death"],
                    bullet_pool=self.enemy_bullets,
                    scene=self
                )

                attack_data = []
                for i in range(len(enemy.attack_data)):
                    if enemy.attack_data[i][0] == "wide_ring":
                        _, bul_num, ring_num, bul_data, spd, s_time, delay, a_speed, d_angle, rand_cnt = \
                        enemy.attack_data[i]
                        attack_data.extend(
                        AttackFunctions.wide_ring
                            (
                                number_of_bullets=bul_num,
                                number_of_rings=ring_num,
                                bullet_data=BulletData(
                                    SpriteSheet(bul_data[0]).crop((bul_data[1], bul_data[2])),
                                    Collider(bul_data[3], bul_data[4])
                                ),
                                speed=spd,
                                start_time=s_time,
                                delay=delay,
                                angular_speed=a_speed,
                                delta_angle=d_angle,
                                rand_center=rand_cnt
                            )
                        )
                    elif enemy.attack_data[i][0] == "long_random":
                        _, bul_num, rand_num, bul_data, spd, s_time, delay, a_speed, rand_cnt = \
                        enemy.attack_data[i]
                        attack_data.extend(
                        AttackFunctions.long_random
                            (
                                number_of_bullets=bul_num,
                                number_of_randoms=rand_num,
                                bullet_data=BulletData(
                                    SpriteSheet(bul_data[0]).crop((bul_data[1], bul_data[2])),
                                    Collider(bul_data[3], bul_data[4])
                                ),
                                speed=spd,
                                start_time=s_time,
                                delay=delay,
                                angular_speed=a_speed,
                                rand_center=rand_cnt
                            )
                        )
                    elif enemy.attack_data[i][0] == "wide_cone":
                        _, bul_num, cone_num, bul_data, angle, spd, d_angle, s_time, delay, a_speed = enemy.attack_data[i]
                        attack_data.extend(
                            AttackFunctions.wide_cone(
                                number_of_bullets=bul_num,
                                number_of_cones=cone_num,
                                bullet_data=BulletData(
                                    SpriteSheet(bul_data[0]).crop((bul_data[1], bul_data[2])),
                                    Collider(bul_data[3], bul_data[4])
                                ),
                                angle=angle,
                                speed=spd,
                                delta_angle=d_angle,
                                start_time=s_time,
                                delay=delay,
                                angular_speed=a_speed,
                                player=self.player,
                                enemy=enemy
                            )
                        )

                enemy.attack_data = sorted(attack_data, key=lambda x: x[1])

                self.enemies.append(enemy)
                self.enemy_count += 1

        ei = 0    
        self.agent.state.enemyCoord = [mlData.emptyCoord]*mlData.maxEnemies 
        mlData.enemyLine = -1
        for enemy in self.enemies:
            enemy.update()
            enemy.move()
            self.agent.state.updateEnemy(enemy,ei)
            ei +=1
            
        for bullet in self.player.bullets:
            on_screen = bullet.move(delta_time)
            if not on_screen:
                self.player.bullets.remove(bullet)
                del bullet

        for item in self.items:
            on_screen = item.move(delta_time, self.player)
            if not on_screen:
                self.items.remove(item)
                del item

        for effect in self.effects:
            ended = not effect.update(delta_time)
            if ended:
                self.effects.remove(effect)
                del effect

        if self.bullet_cleaner:
            self.bullet_cleaner.update(self.enemy_bullets, self, delta_time)
            if self.bullet_cleaner.kill:
                del self.bullet_cleaner
                self.bullet_cleaner = None

        ebi=0
        self.agent.state.bulletCoord = [mlData.emptyCoord]*mlData.maxBullets
        #print(len(self.enemy_bullets), end = ' ')
        for bullet in self.enemy_bullets:
        
            on_screen = bullet.move(delta_time)
        
            if not on_screen or (mlData.difficulty[0] and ebi//mlData.difficulty[1]):
                self.enemy_bullets.remove(bullet)
            self.agent.newState.updateBullet(self.agent,bullet,ebi)
            ebi +=1
            
        self.agent.state.updateTime(self.time)
        self.player.update()
        self.agent.newState.playerCoord= self.player.position.coords
        #1000 lines of code to update agent state above
        #-------------------------------------------------------------------------------------------------
        #RL continues here:
        self.agent.returnR()
        
        if mlData.mode == 'EDDQN':
            self.agent.addReplay()

        self.agent.reviewAction()
        
        if mlData.mode == 'EDDQN':
            self.agent.expReplay()


        if mlData.timeStep % mlData.QTargetStep == 0:
            self.agent.updateQtarget()

        if self.agent.terminal:
            plotter.plot_highest_scores(mlData.finalScoreArray)
            self.player.switch_to_scoreboard()    
        else:
            mlData.timeStep +=1
        #self.agent.state = self.agent.newState



#---------------------------------------------------------------------------------------------------------



    @render_fps
    def render(self, screen, clock):
        screen.fill((0, 0, 0), rect=GAME_ZONE)

        self.agent.ring.visualise(screen,(100,0,0))
        #

        for bullet in self.player.bullets:
            self.bullet_group.add(bullet.get_sprite())

        for bullet in self.enemy_bullets:
            self.bullet_group.add(bullet.get_sprite())
        '''
        for bulletPos in self.agent.state.bulletPos:
            bulletCollider = Collider(10,bulletPos)
            bulletCollider.visualise(screen,(0,255,0))

        for enemyPos in self.agent.state.enemyPos:
            enemyCollider = Collider(10,enemyPos)
            enemyCollider.visualise(screen,(0,0,255))
        '''
        if mlData.hitBoxStatus== True:
            for bulletCoord in self.agent.state.bulletCoord:
                pygame.draw.circle(screen, (0,100,0),(bulletCoord[0],bulletCoord[1]),10)

            for enemyCoord in self.agent.state.enemyCoord:
                pygame.draw.circle(screen, (0,0,100),enemyCoord,20)
            
            pygame.draw.line(screen,mlData.enemyLineColor,(0,mlData.enemyLine),(700,mlData.enemyLine))
            #pygame.draw.circle(screen, (0,0,255),self.player.position.coords,mlData.proxyRange)

        for item in self.items:
            self.item_group.add(item.get_sprite())

        for effect in self.effects:
            self.effect_group.add(effect.get_sprite())

        self.hud_group.add(self.bg)

        high_score = db_module.get_highscore()[0][0]

        if not high_score:
            high_score = 0

        hi_score_label = self.font.render(f"HiScore:    {format(high_score if high_score > self.player.points else self.player.points, '09d')}", True, (255, 255, 255)).convert_alpha()

        score_label = self.font.render(f"Score:    {format(self.player.points, '09d')}", True, (255, 255, 255)).convert_alpha()

        power_label = self.font.render(f"Power:    {format(round(self.player.power, 2), '.2f')} / 4.00", True,
                                       (255, 255, 255)).convert_alpha()

        hp_label = self.font.render(f"Player:   {'★' * self.player.hp}", True, (255, 255, 255)).convert_alpha()

        player_sprite = self.player.get_sprite()
        if self.player.slow or (self.player.reviving and self.player.invincibility_timer % 40 > 30):
            player_sprite.image.set_alpha(150)

        self.entity_group.add(player_sprite)

        for enemy in self.enemies:
            self.entity_group.add(enemy.get_sprite())

        self.entity_group.draw(screen)
        self.item_group.draw(screen)
        self.bullet_group.draw(screen)
        self.effect_group.draw(screen)

        if self.bullet_cleaner:
            screen.blit(self.bullet_cleaner.get_sprite(), (self.bullet_cleaner.collider.position - self.bullet_cleaner.collider.radius).to_tuple())

        if self.player.slow:
            player_hitbox_sprite = self.player.get_hitbox_sprite()
            screen.blit(player_hitbox_sprite, (self.player.position - (Vector2(*player_hitbox_sprite.get_size())) // 2).to_tuple())

        self.hud_group.draw(screen)

        screen.blit(hi_score_label, (GAME_ZONE[0] + GAME_ZONE[2] + 13, 160))
        screen.blit(score_label, (GAME_ZONE[0] + GAME_ZONE[2] + 50, 210))
        screen.blit(hp_label, (GAME_ZONE[0] + GAME_ZONE[2] + 50, 280))
        screen.blit(power_label, (GAME_ZONE[0] + GAME_ZONE[2] + 50, 330))

        self.effect_group.empty()
        self.entity_group.empty()
        self.item_group.empty()
        self.bullet_group.empty()
        self.bullet_group.empty()
        self.hud_group.empty()