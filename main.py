import asyncio
import pprint
import typing

import dico
import dico_interaction
from dico_interaction import InteractionClient, InteractionCommand, InteractionContext

import json
import os

with open("data/mainData.json", "r") as f:
    mainData = json.load(f)

bot = dico.Client(token=mainData['token'], intents=dico.Intents.full())
interaction = dico_interaction.InteractionClient(client=bot, auto_register_commands=True)

runtimes = {}

colors = {
    "blank": "<:blank:924156268317392926>",
    "red": "🟥",
    "orange": "🟧",
    "yellow": "🟨",
    "green": "🟩",
    "blue": "🟦",
    "purple": "🟪",
    "brown": "🟫",
    "black": "⬛",
    "white": "⬜"
}

where = {
    "start": 3,
    "update": 4,
    "copy": 5
}

class Sprite:
    def __init__(self, name: str, size: list):
        self.name = name
        self.size = size
        self.shape = [['blank' for j in range(5)] for i in range(5)]

    def render(self, rowIndex: int = None, columnIndex: int = None):
        if rowIndex is None and columnIndex is None:
            return '\n'.join([''.join(colors[c] for c in row) for row in self.shape])
        elif columnIndex is None:
            return ''.join(colors[c] for c in self.shape[rowIndex])
        elif rowIndex is None:
            return '\n'.join(colors[c] for c in [row[columnIndex] for row in self.shape])
        else:
            return colors[self.shape[rowIndex][columnIndex]]

    @staticmethod
    def from_json(json_data: dict):
        sprite = Sprite(json_data["name"], [5, 5])
        for row in json_data["shape"]:
            sprite.shape.append(row)
        return sprite


class Codes:
    def __init__(self, whenStarted = None, whenUpdated = None, whenDuplicated = None):
        if whenUpdated is None:
            whenUpdated = []
        if whenDuplicated is None:
            whenDuplicated = []
        if whenStarted is None:
            whenStarted = []
        self.whenStarted = whenStarted
        self.whenUpdated = whenUpdated
        self.whenDuplicated = whenDuplicated

    def getAsString(self):
        a = []
        for j in [self.whenStarted, self.whenUpdated, self.whenDuplicated]:
            toAdd = []
            for num, i in enumerate(j):
                if i[0] == "move":
                    if i[1] == 0:
                        toAdd.append(f"오른쪽으로 {i[2]}칸 이동하기")
                    elif i[1] == 1:
                        toAdd.append(f"아래로 {i[2]}칸 이동하기")
                    elif i[1] == 2:
                        toAdd.append(f"왼쪽으로 {i[2]}칸 이동하기")
                    elif i[1] == 3:
                        toAdd.append(f"위로 {i[2]}칸 이동하기")
                elif i[0] == "moveTo":
                    toAdd.append(f"세로: {i[1][0]}, 가로: {i[1][1]}(으)로 이동하기")
                elif i[0] == "turn":
                    if i[1] == 0:
                        toAdd.append(f"오른쪽으로 90도 회전하기")
                    elif i[1] == 1:
                        toAdd.append(f"왼쪽으로 90도 회전하기")
                elif i[0] == "display":
                    if i[1] == True:
                        toAdd.append(f"숨기기")
                    else:
                        toAdd.append(f"보이기")
                elif i[0] == "wait":
                    toAdd.append(f"{i[1]}틱 기다리기")
                elif i[0] == "duplicate":
                    toAdd.append(f"{i[1][1]}, {i[1][0]} 칸에 자신 복제하기")
                toAdd[-1] = f"{num+1}. {toAdd[-1]}"
            a.append("\n".join(toAdd))
        return a


    def setSprite(self, sprite: "SpriteInProject"):
        self.sprite = sprite


    @staticmethod
    def move(direction: int, distance: int):
        return ["move", direction, distance]

    @staticmethod
    def turn(direction: int):
        return ["turn", direction]

    @staticmethod
    def display(transparent: bool):
        return ["display", transparent]

    @staticmethod
    def wait(duration: int):
        return ["wait", duration]

    @staticmethod
    def moveTo(location: list):
        return ["moveTo", location]

    @staticmethod
    def duplicate(location: list):
        return ["duplicate", location]

    @staticmethod
    def from_json(json_data: list):
        return Codes(whenStarted=json_data[0], whenUpdated=json_data[1], whenDuplicated=json_data[2])

class SpriteInProject(Sprite):
    def __init__(self, sprite: Sprite, position: list, id: int, code: Codes = None):
        super().__init__(sprite.name, sprite.size)
        self.id = id
        self.shape = sprite.shape
        self.position = position
        if code is None:
            self.code = Codes()
        else:
            self.code = code

    def getDotsInScreen(self):
        return {
            y + self.position[1]: {x + self.position[0]: color for x, color in enumerate(row) if color != 'blank'}
            for y, row in enumerate(self.shape) if row != ['blank'] * 5
        }

class Project:
    def __init__(self, name: str, backgroundColor: str, sprites: list[SpriteInProject]):
        self.name = name
        self.backgroundColor = backgroundColor
        self.sprites = sprites
        self.display = [[backgroundColor for j in range(27)] for i in range(14)]

    def redraw(self):
        self.display = [[self.backgroundColor for j in range(27)] for i in range(14)]
        for sprite in self.sprites:
            for y, row in sprite.getDotsInScreen().items():
                for x, color in row.items():
                    self.display[y][x] = color

    def render(self):
        return '\n'.join([''.join(colors[c] for c in row) for row in self.display])

class SpriteInRuntime(SpriteInProject):
    def __init__(self, sprite: SpriteInProject):
        self.sprite = sprite
        self.position = [0, 0]
        self.shape = sprite.shape
        self.visible = True
        self.tick = 0
        self.remainingCode = {}

        for code in self.sprite.code.whenStarted:
            if code[0] == "wait":
                if self.remainingCode.get(self.tick + code[1]) is None:
                    self.remainingCode[self.tick + code[1]] = code
                else:
                    self.remainingCode[self.tick + code[1]].extend(code[1])
                break
            else:
                self.run(code)

    def getDotsInScreen(self):
        if self.visible:
            return {
                y + self.position[1]: {x + self.position[0]: color for x, color in enumerate(row) if color != 'blank'}
                for y, row in enumerate(self.shape) if row != ['blank'] * 5
            }
        else:
            return {}


    def nextTick(self):
        self.tick += 1
        if self.remainingCode.get(self.tick):
            for code in self.remainingCode.get(self.tick, []):
                if code[0] == "wait":
                    if self.remainingCode.get(self.tick + code[1]) is None:
                        self.remainingCode[self.tick + code[1]] = code
                    else:
                        self.remainingCode[self.tick + code[1]].extend(code[1])
                    break
                else:
                    self.run(code)
            del self.remainingCode[self.tick]
        for code in self.sprite.code.whenUpdated:
            if code[0] == "wait":
                if self.remainingCode.get(self.tick + code[1]) is None:
                    self.remainingCode[self.tick + code[1]] = code
                else:
                    self.remainingCode[self.tick + code[1]].extend(code[1])
                break
            else:
                self.run(code)


    def rotate(self, direction: int):
        if direction == 1:
            # turn 90 degrees right
            a = []
            for y in range(5):
                b = []
                for x in range(5):
                    b.append(self.shape[x][y])
                a.append(b)
            self.shape = a
        if direction == 2:
            self.shape = [list(reversed(row)) for row in self.shape]
        if direction == 3:
            # turn 90 degrees left
            a = []
            for y in range(5):
                b = []
                for x in range(5):
                    b.append(self.shape[4-x][4-y])
                a.append(b)
            self.shape = a

    def run(self, code: list):
        if code[0] == "move":
            if code[1] == 0:
                self.position[0] += code[2]
            elif code[1] == 1:
                self.position[1] += code[2]
            elif code[1] == 2:
                self.position[0] -= code[2]
            elif code[1] == 3:
                self.position[1] -= code[2]
        elif code[0] == "turn":
            self.rotate(code[1])
        elif code[0] == "display":
            self.sprite.visible = code[1]
        elif code[0] == "wait":
            pass
        elif code[0] == "moveTo":
            self.position = code[1]
        elif code[0] == "duplicate":
            DuplicatedSprite(self, code[1])


class DuplicatedSprite(SpriteInRuntime):
    def __init__(self, sprite: SpriteInRuntime, position: list):
        self.sprite = sprite.sprite
        self.position = position
        self.shape = sprite.shape
        self.visible = sprite.visible
        self.tick = 0
        self.remainingCode = {}
        for code in self.sprite.code.whenDuplicated:
            if code[0] == "wait":
                if self.remainingCode.get(self.tick + code[1]) is None:
                    self.remainingCode[self.tick + code[1]] = code
                else:
                    self.remainingCode[self.tick + code[1]].extend(code[1])
                break
            elif code[0] == "duplicate":
                continue
            else:
                self.run(code)

    def run(self, code: list):
        if code[0] == "duplicate":
            return
        else:
            super().run(code)


class Runtime:
    def __init__(self, project: Project, bot: dico.Client, ctx: dico_interaction.InteractionContext, embed: dico.Embed):
        self.project = project
        self.sprites = [SpriteInRuntime(sprite) for sprite in self.project.sprites]
        self.ctx = ctx
        self.bot = bot
        self.embed = embed
        self.isStopped = False
        self.tick = 0

    async def start(self):
        while (not self.isStopped) and self.tick <= 100:
            scene = [["black" for i in range(27)] for i in range(14)]
            self.tick += 1
            for sprite in self.sprites:
                sprite.nextTick()
                dots = sprite.getDotsInScreen()
                print(dots)
                for y, row in dots.items():
                    for x, color in row.items():
                        try:
                            scene[y][x] = color
                        except IndexError:
                            pass
            await self.render(scene)
            def check(ictx: dico_interaction.InteractionContext):
                return ictx.author.id == self.ctx.author.id and ictx.channel_id == self.ctx.channel_id and ictx.data.custom_id.endswith(str(self.ctx.id))
            try:
                await interaction.wait_interaction(timeout=0.8, check=check)
                self.isStopped = True
            except asyncio.TimeoutError:
                pass
            else:
                self.isStopped = True

    async def stop(self):
        self.isStopped = True

    async def render(self, scene):
        self.embed.fields[1].name = "".join([colors[txt] for txt in scene[0]])
        self.embed.fields[1].value = "".join(["".join([colors[txt] for txt in scene[i]]) for i in range(1, 7)])
        self.embed.fields[1].name = "".join([colors[txt] for txt in scene[7]])
        self.embed.fields[1].value = "".join(["".join([colors[txt] for txt in scene[i]]) for i in range(8, 14)])
        await self.ctx.edit_original_response(embed=self.embed)


    def addSprite(self, sprite: SpriteInRuntime):
        self.sprites.append(sprite)



class ButtonGetter:
    def __init__(self, messageID: int):
        self.messageID = messageID
        self.usedNum = 0
        self.up = dico.Button(style=dico.ButtonStyles.PRIMARY, emoji="⬆️", custom_id=f"b_up_{messageID}")
        self.down = dico.Button(style=dico.ButtonStyles.PRIMARY, emoji="⬇️", custom_id=f"b_down_{messageID}")
        self.left = dico.Button(style=dico.ButtonStyles.PRIMARY, emoji="⬅️", custom_id=f"b_left_{messageID}")
        self.right = dico.Button(style=dico.ButtonStyles.PRIMARY, emoji="➡️", custom_id=f"b_right_{messageID}")

        self.accept = dico.Button(style=dico.ButtonStyles.SUCCESS, emoji="✅", custom_id=f"b_accept_{messageID}")
        self.decline = dico.Button(style=dico.ButtonStyles.DANGER, emoji="❌", custom_id=f"b_decline_{messageID}")

        self.save = dico.Button(style=dico.ButtonStyles.SUCCESS, label="저장", emoji="💾", custom_id=f"b_save_{messageID}")
        self.delete = dico.Button(style=dico.ButtonStyles.DANGER, label="삭제", emoji="🗑️", custom_id=f"b_delete_{messageID}")

        self.erase = dico.Button(style=dico.ButtonStyles.DANGER, label="지우기", custom_id=f"b_erase_{messageID}")

    def color(self, color: str):
        return dico.Button(style=dico.ButtonStyles.SECONDARY, emoji=colors[color], custom_id=f"b_{color}_{self.messageID}")

    @property
    def placeholder(self):
        self.usedNum += 1
        return dico.Button(style=dico.ButtonStyles.SECONDARY, label=" ", custom_id=f"pl{self.usedNum}", disabled=True)


class Asker:
    def __init__(self, bot: dico.Client, ctx: InteractionContext):
        self.bot = bot
        self.ctx = ctx

    async def direction(self, embed: dico.Embed):
        embed.fields[6].value = "방향을 선택해주세요: (0: 오른쪽, 1: 아래쪽, 2: 왼쪽, 3: 위쪽)"
        await self.ctx.edit_original_response(embed=embed)
        def scheck(msg: dico.Message):
            if msg.channel_id == self.ctx.channel_id and msg.author.id == self.ctx.author.id:
                if msg.content.strip() in ["0", "1", "2", "3"]:
                    return True
                else:
                    # embed.fields[6].value = "다시 입력해주세요."
                    # await self.ctx.edit_original_response(embed=embed)
                    return False
        msg = await self.bot.wait("message_create", timeout=30, check=scheck)
        dir = int(msg.content.strip())
        return dir

    async def location(self, embed: dico.Embed):
        embed.fields[6].value = "위치를 세로, 가로 순으로 입력해주세요. (예: 1, 2)"
        await self.ctx.edit_original_response(embed=embed)
        def scheck(msg: dico.Message):
            if msg.channel_id == self.ctx.channel_id and msg.author.id == self.ctx.author.id:
                split = [i.strip() for i in msg.content.strip().split(',')]
                if len(split) != 2:
                    print("잘못된 입력입니다. 다시 입력해주세요.")
                    return False
                if not split[0].isdecimal() or not split[1].isdecimal():
                    print("잘못된 입력입니다. 다시 입력해주세요.")
                    return False
                if int(split[0]) < 0 or int(split[1]) < 0:
                    print("숫자가 너무 작습니다. 다시 시도해주세요.")
                    return False
                return True
            return False
        return [int(i) for i in (await bot.wait("message_create", timeout=30, check=scheck)).content.strip().split(', ')]


@interaction.command(name="검색", description="프로젝트를 검색합니다.")
async def search(ctx: InteractionContext, id: int):
    # todo
    pass


@interaction.command(name="프로젝트", description="프로젝트", subcommand="재생", subcommand_description="프로젝트를 재생합니다.", )
async def playProgram(ctx: InteractionContext, id: int):
    if os.path.isfile(f"data/projects/{ctx.author.id}/{id}.json"):
        with open(f"data/projects/{ctx.author.id}/{id}.json", "r") as f:
            data = json.load(f)
            sprites = []
            for spriteData in data['sprites']:
                with open(f"data/sprites/{ctx.author.id}/{spriteData['id']}.json", "r") as f:
                    original = json.load(f)
                sprites.append(SpriteInProject(Sprite.from_json(original), position=[0, 0], id=spriteData['id'], code=Codes.from_json(spriteData['code'])))
        project = Project(name=data['name'], sprites=sprites, backgroundColor="black")
    else:
        await ctx.send("파일이 존재하지 않습니다.")
        return
    embed = dico.Embed(title=f"{data['name']} 프로젝트 재생", description=f"이름: {data['name']}\nID: {id}", color=0x00ff00)
    bg = ButtonGetter(int(ctx.id))
    embed.add_field(name="Screen", value="- " * 10)
    screen = project.render()
    lines = screen.split("\n")
    embed.add_field(name=lines[0], value="\n".join(lines[1:7]), inline=False)
    embed.add_field(name=lines[7], value="\n".join(lines[8:14]), inline=False)
    runtime = Runtime(project, bot, ctx, embed)
    message = await ctx.send(embed=embed, components=[
        dico.ActionRow(dico.Button(style=dico.ButtonStyles.PRIMARY, emoji="⏹️", custom_id=f"b_stop_{ctx.id}"))
    ])
    await runtime.start()
    def check(ictx: InteractionContext):
        print(ictx.author == ctx.author, ictx.data.custom_id.endswith(str(ctx.id)), (ictx.data.custom_id.startswith("b_")))
        return ictx.author == ctx.author and ictx.data.custom_id.endswith(str(ctx.id)) and (ictx.data.custom_id.startswith("b_"))
    ictx: InteractionContext = await interaction.wait_interaction(timeout=80, check=check)
    message = await ctx.send(embed=embed, components=[
        dico.ActionRow(dico.Button(style=dico.ButtonStyles.PRIMARY, emoji="⏹️", custom_id=f"b_stop_{ctx.id}", disabled=True))
    ])
    await ictx.send("정지되었습니다.")
    await runtime.stop()
    return


@interaction.command(name="프로젝트", description="프로젝트", subcommand="생성", subcommand_description="프로젝트를 생성합니다.", )
async def cProgram(ctx: InteractionContext, name: str):
    embed = dico.Embed(title=f"{name} 프로젝트 생성", description=f"이름: {name}", color=0x00ff00)
    project = Project(name=name, sprites=[], backgroundColor="black")
    bg = ButtonGetter(int(ctx.id))
    asker = Asker(bot, ctx)

    codeSelect = dico.SelectMenu(custom_id=f"s_code_{ctx.id}", options=[
        dico.SelectOption(label="n칸 이동하기", value="move"),
        dico.SelectOption(label="특정 칸으로 이동하기", value="moveTo"),
        dico.SelectOption(label="바라보기", value="turn"),
        dico.SelectOption(label="보이기", value="show"),
        dico.SelectOption(label="숨기기", value="hide"),
        dico.SelectOption(label="n틱 기다리기", value="wait"),
        dico.SelectOption(label="복제하기", value="duplicate")
    ], placeholder="행동을 선택하세요...", disabled=True)

    eventSelect = dico.SelectMenu(custom_id=f"s_event_{ctx.id}", options=[
        dico.SelectOption(label="시작 버튼을 눌렀을 때", value="start"),
        dico.SelectOption(label="1틱마다", value="update"),
        dico.SelectOption(label="복제되었을 때", value="copy")
    ], placeholder="이벤트를 선택하세요...", disabled=True)

    spriteSelect = dico.SelectMenu(custom_id=f"s_sprite_{ctx.id}", options=[
        dico.SelectOption(label="스프라이트 추가", value="add", description="스프라이트를 추가합니다.")
    ], placeholder="스프라이트를 선택하세요...")

    embed.add_field(name="Screen", value="- "*10)
    screen = project.render()
    lines = screen.split("\n")
    embed.add_field(name=lines[0], value="\n".join(lines[1:7]), inline=False)
    embed.add_field(name=lines[7], value="\n".join(lines[8:14]), inline=False)
    embed.add_field(name="시작 버튼을 눌렀을 때", value=".", inline=False)
    embed.add_field(name="1틱마다", value=".", inline=False)
    embed.add_field(name="복제되었을 때", value=".", inline=False)
    embed.add_field(name="Console", value="DisAnimator", inline=False)
    selectedLine = 0
    selectedEvent = "start" # or copy, update
    selectedSprite = 0

    message = await ctx.send(embed=embed, components=[
        dico.ActionRow(bg.up, bg.save, bg.delete, dico.Button(style=dico.ButtonStyles.PRIMARY, label="미리보기", emoji="🎥", custom_id=f"b_preview_{int(ctx.id)}")),
        dico.ActionRow(bg.down, bg.erase),
        dico.ActionRow(codeSelect),
        dico.ActionRow(eventSelect),
        dico.ActionRow(spriteSelect)
    ])
    def check(ictx: InteractionContext):
        return ictx.author == ctx.author and ictx.data.custom_id.endswith(str(ctx.id)) and (ictx.data.custom_id.startswith("b_") or ictx.data.custom_id.startswith("s_"))

    spritesInDB = os.listdir(f'data/sprites/{ctx.author.id}')

    while True:
        unchanged = False
        ictx: InteractionContext = await interaction.wait_interaction(timeout=60, check=check)
        customID = ictx.data.custom_id
        if ictx.data.component_type.is_type("SELECT_MENU"):
            if customID == spriteSelect.custom_id:
                if ictx.data.values[0] == "add":
                    embed.fields[6].value = "추가할 스프라이트의 ID를 입력해주세요."
                    await ctx.edit_original_response(embed=embed)
                    def scheck(msg: dico.Message):
                        if msg.channel_id == ctx.channel_id and msg.author.id == ctx.author.id:
                            if msg.content.strip().isdecimal():
                                if f"{msg.content.strip()}.json" in spritesInDB:
                                    return True
                                else:
                                    # ictx.send("DB에 존재하지 않는 스프라이트입니다. 다시 입력해주세요.")
                                    pass
                            else:
                                # ictx.send("다시 입력해주세요.")
                                pass
                        return
                    asmsg = await bot.wait("message_create", timeout=30, check=scheck)
                    with open(f'data/sprites/{ctx.author.id}/{asmsg.content.strip()}.json') as f:
                        project.sprites.append(SpriteInProject(Sprite.from_json(json.load(f)), position=[0, 0], id=int(asmsg.content.strip())))
                        spriteSelect.options.insert(-1,
                            dico.SelectOption(label=project.sprites[-1].name, value=str(len(project.sprites) - 1),
                                              description=f"{project.sprites[-1].name}"),
                        )
                        selectedSprite = len(project.sprites) - 1
                    embed.fields[6].value = "완료되었습니다."
                else:
                    selectedSprite = int(ictx.data.values[0])

                spriteSelect.options[selectedSprite].description = f"{project.sprites[selectedSprite].name} (선택됨)"
                codeSelect.disabled = False
                eventSelect.disabled = False


            elif customID == eventSelect.custom_id:
                embed.fields[where[selectedEvent]].value = embed.fields[where[selectedEvent]].value.replace(":arrow_forward: ", "")
                selectedEvent = ictx.data.values[0]
                selectedLine = 0
            elif customID == codeSelect.custom_id:
                if selectedEvent == "start":
                    codes = project.sprites[selectedSprite].code.whenStarted
                elif selectedEvent == "update":
                    codes = project.sprites[selectedSprite].code.whenUpdated
                else:
                    codes = project.sprites[selectedSprite].code.whenDuplicated
                if ictx.data.values[0] == "move":
                    embed.fields[6].value = "움직일 칸을 입력해주세요. (예: 1)"
                    await ctx.edit_original_response(embed=embed)
                    def scheck(msg: dico.Message):
                        if msg.channel_id == ctx.channel_id and msg.author.id == ctx.author.id:
                            if msg.content.strip().isdecimal():
                                a = int(msg.content.strip())
                                if a > 28 or a < 0:
                                    # await ictx.send("잘못된 입력입니다. 다시 입력해주세요.")
                                    pass
                                return True
                            else:
                                # await ictx.send("다시 입력해주세요.")
                                return False

                    amomsg = await bot.wait("message_create", timeout=60, check=scheck)
                    codes.append(Codes.move(await asker.direction(embed), int(amomsg.content.strip())))
                elif ictx.data.values[0] == "turn":
                    embed.fields[6].value = "각도를 선택해주세요. (1: 오른쪽으로 90, 2: 오른쪽으로 180, 3: 왼쪽으로 90)"
                    await ctx.edit_original_response(embed=embed)
                    def scheck(msg: dico.Message):
                        if msg.channel_id == ctx.channel_id and msg.author.id == ctx.author.id:
                            if msg.content.strip() in ["1", "2", "3"]:
                                return True
                            else:
                                # embed.fields[6].value = "다시 입력해주세요."
                                # await self.ctx.edit_original_response(embed=embed)
                                return False
                    msg = await bot.wait("message_create", timeout=60, check=scheck)
                    deg = int(msg.content.strip())
                    codes.append(Codes.turn(deg))
                elif ictx.data.values[0] == "moveTo":
                 codes.append(Codes.moveTo(await asker.location(embed)))
                elif ictx.data.values[0] == "duplicate":
                    if selectedEvent == "copy":
                        embed.fields[6].value = "복제되었을 때는 재복제할 수 없어요!"
                        await ctx.edit_original_response(embed=embed)
                        unchanged = True
                    else:
                        codes.append(Codes.duplicate(await asker.location(embed)))
                elif ictx.data.values[0] == "show":
                    codes.append(Codes.display(False))
                elif ictx.data.values[0] == "hide":
                    codes.append(Codes.display(True))
                elif ictx.data.values[0] == "wait":
                    await ictx.send("시간을 입력해주세요. (예: 5)")
                    def scheck(msg: dico.Message):
                        if msg.channel_id == ctx.channel_id and msg.author.id == ctx.author.id:
                            if msg.content.strip().isdecimal():
                                a = int(msg.content.strip())
                                if a > 20 or a < 0:
                                    # await ictx.send("잘못된 입력입니다. 다시 입력해주세요.")
                                    return False
                                return True
                            else:
                                # await ictx.send("다시 입력해주세요.")
                                return False

                    timemsg = await bot.wait("message_create", timeout=30, check=scheck)
                    codes.append(Codes.wait(int(timemsg.content.strip())))
                elif ictx.data.values[0] == "backgroundColor":
                    await ictx.send("색상을 이모지로 입력해주세요.")
                if not unchanged:
                    if len(codes) > 1:
                        selectedLine += 1

        elif ictx.data.component_type.is_type("BUTTON"):
            try:
                if selectedEvent == "start":
                    codes = project.sprites[selectedSprite].code.whenStarted
                elif selectedEvent == "update":
                    codes = project.sprites[selectedSprite].code.whenUpdated
                else:
                    codes = project.sprites[selectedSprite].code.whenDuplicated
            except IndexError:
                embed.fields[6].value = "선택된 스프라이트가 없습니다."
                await ctx.edit_original_response(embed=embed)
                continue
            if customID == bg.up.custom_id:
                selectedLine -= 1
            elif customID == bg.down.custom_id:
                selectedLine += 1
            elif customID == bg.erase.custom_id:
                codes = codes.pop(selectedLine)
                print(project.sprites[selectedSprite].code.whenStarted)
                if selectedLine > 0:
                    selectedLine -= 1
            elif customID == f"b_preview_{int(ctx.id)}":
                if runtimes.get(ctx.id) is None:
                    runtime = Runtime(project, bot, ctx, embed)
                    await runtime.start()
                    runtimes[ctx.id] = runtime
                else:
                    await runtimes[ctx.id].stop()
            elif customID == bg.save.custom_id:
                if not os.path.isdir(f"data/projects/{ctx.author.id}"):
                    os.mkdir(f"data/projects/{ctx.author.id}")
                files = os.listdir(f"data/projects/{ctx.author.id}")
                with open(f"data/projects/{ctx.author.id}/{len(files)}.json", "w") as f:
                    # save Project to json
                    json.dump({
                        "name": project.name,
                        "sprites": [
                            {'id': sprite.id,
                             'code': [
                                 sprite.code.whenStarted, sprite.code.whenUpdated, sprite.code.whenDuplicated
                             ]} for sprite in project.sprites],
                    }, f, indent=2)
                embed.fields[6].value = f"저장되었습니다, ID는 `{len(files)}`입니다!"
                await ctx.edit_original_response(embed=embed)
            elif customID == bg.delete.custom_id:
                await runtime.stop()
                embed.fields[6].value = "삭제되었습니다."
                return await ctx.edit_original_response(embed=embed)


        codesAsString = project.sprites[selectedSprite].code.getAsString()
        for i, codeS in enumerate(codesAsString):
            if codeS:
                embed.fields[i + 3].value = codeS
            else:
                embed.fields[i + 3].value = "1. 코드가 없어요!"
        embed.fields[where[selectedEvent]].value = embed.fields[where[selectedEvent]].value.replace(str(selectedLine + 1)+'.', ":arrow_forward:")
        await ctx.edit_original_response(embed=embed, components=[
            dico.ActionRow(bg.up, bg.save, bg.delete,
                           dico.Button(style=dico.ButtonStyles.PRIMARY, label="미리보기", emoji="🎥",
                                       custom_id=f"b_preview_{int(ctx.id)}")),
            dico.ActionRow(bg.down, bg.erase),
            dico.ActionRow(codeSelect),
            dico.ActionRow(eventSelect),
            dico.ActionRow(spriteSelect)
        ])


@interaction.slash(name="스프라이트", description="스프라이트", subcommand="창고", subcommand_description="저장되어 있는 스프라이트를 보여줍니다.", )
async def seeSprites(ctx: InteractionContext):
    if not os.path.isdir(f"data/projects/{ctx.author.id}"):
        os.mkdir(f"data/projects/{ctx.author.id}")
    files = os.listdir(f"data/projects/{ctx.author.id}")
    embed = dico.Embed(title=str(ctx.author)+"님의 스프라이트 창고")
    for i, file in enumerate(files):
        with open(f"data/projects/{ctx.author.id}/{file}", "r") as f:
            sprite = Sprite.from_json(json.load(f))
            embed.add_field(name=f"ID: {i}. {sprite.name}", value=sprite.render())
    await ctx.send(embed=embed)


@interaction.slash(name="스프라이트", description="스프라이트", subcommand="생성", subcommand_description="스프라이트를 생성합니다.")
async def addSprite(ctx: InteractionContext, name: str):
    cid = int(ctx.id)
    embed = dico.Embed(title="스프라이트 생성!", description=f"이름: {name}", color=0x00ff00)
    sprite = Sprite(name, [5, 5])
    # [x, y]
    selected = [0, 0]
    showing = colors['blank'] * (selected[0] + 1) + "🔽" + colors['blank'] * (5 - selected[0] - 1) + "\n" + "\n".join([
        ("▶️" if i == selected[1] else colors['blank']) + sprite.render(rowIndex=i) for i in range(5)
    ])
    embed.add_field(name="Design", value=showing)
    bg = ButtonGetter(cid)
    message = await ctx.send(embed=embed, components=[
        dico.ActionRow(bg.save, bg.delete),
        dico.ActionRow(bg.placeholder, bg.up, bg.placeholder),
        dico.ActionRow(bg.left, bg.down, bg.right),
        dico.ActionRow(bg.color("red"), bg.color("orange"), bg.color("yellow"), bg.color("green"), bg.color("blue")),
        dico.ActionRow(bg.color("purple"), bg.color("brown"), bg.color("black"), bg.color("white"), bg.erase)
    ])
    clicked = {
        "delete": 0
    }
    def check(ictx: InteractionContext):
        return ictx.author == ctx.author and ictx.data.custom_id.endswith(str()) and ictx.data.custom_id.startswith("b_")
    while True:
        ictx: InteractionContext = await interaction.wait_interaction(timeout=30, check=check)
        customID = ictx.data.custom_id
        if customID == bg.up.custom_id:
            selected[1] = (selected[1] - 1) % 5
        elif customID == bg.down.custom_id:
            selected[1] = (selected[1] + 1) % 5
        elif customID == bg.left.custom_id:
            selected[0] = (selected[0] - 1) % 5
        elif customID == bg.right.custom_id:
            selected[0] = (selected[0] + 1) % 5
        elif customID == bg.erase.custom_id:
            sprite.shape[selected[1]][selected[0]] = "blank"
        elif customID == bg.save.custom_id:
            if not os.path.isdir(f"data/sprites/{ctx.author.id}"):
                os.mkdir(f"data/sprites/{ctx.author.id}")
            files = os.listdir(f"data/sprites/{ctx.author.id}")
            with open(f"data/sprites/{ctx.author.id}/{len(files)}.json", "w") as f:
                json.dump({
                    "name": name,
                    "shape": sprite.shape
                }, f)
            await ictx.send(f"파일을 저장했어요, 스프라이트의 ID는 `{len(files)}` 입니다!")
            return
        elif customID == bg.delete.custom_id:
            if clicked["delete"] == 1:
                break
            else:
                clicked["delete"] = 2
                await ctx.send("삭제하시려면 한 번 더 눌러주세요.")
        else:
            color = customID.split("_")[1]
            sprite.shape[selected[1]][selected[0]] = color
        showing = colors['blank'] * (selected[0] + 1) + "🔽" + colors['blank'] * (5 - selected[0] - 1) + "\n" + "\n".join([
            ("▶️" if i == selected[1] else colors['blank']) + sprite.render(rowIndex=i) for i in range(5)
        ])
        embed.fields[0].value = showing
        for key in clicked:
            clicked[key] -= 1
        await ictx.send(embed=embed, update_message=True)


@interaction.slash(name="정리", description="clean")
async def clean(ctx: InteractionContext):
    channel: dico.Channel = bot.get(ctx.author.id, "guild")
    channel.bulk_delete_messages(100)


bot.run()

