import discord
from discord.ext import commands
from __main__ import settings, botdata
from cogs.utils.helpers import *
from cogs.utils.clip import *
from cogs.utils import checks
from .mangocog import *
import aiohttp
import asyncio
import os
import re
import chess
import chess.uci
import random
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

class Chess(MangoCog):
    """How about a nice game of chess?

    Any player can challenge another player and create a board. Try ?chess @username#ID to initiate a challenge. Sides chosen at random.

    Use proper chess notation! You can get more info [here](https://en.wikipedia.org/wiki/Chess_notation)

    Type __gg__ to resign a game 
    """
    def __init__(self, bot):
        MangoCog.__init__(self, bot)
        self.chessAI = '/path/to/chess/engine/executable'
   
    def expand_blanks(self,fen):
      def expand(match):
        return ' ' * int(match.group(0))
      return re.compile(r'\d').sub(expand, fen)

    def expand_fen(self,fen):
      expanded = self.expand_blanks(fen)
      return expanded.replace('/', '')
        
    def draw_board(self,n=8, sq_size=(20, 20)):
      from itertools import cycle
      def square(i, j):
        return i * sq_size[0], j * sq_size[1]
      opaque_grey_background = 192, 255
      board = Image.new('LA', square(n, n), opaque_grey_background)
      draw_square = ImageDraw.Draw(board).rectangle
      whites = ((square(i, j), square(i + 1, j + 1))
        for i_start, j in zip(cycle((0, 1)), range(n))
        for i in range(i_start, n, 2))
      for white_square in whites:
        draw_square(white_square, fill='white')
      return board

    def legend(self, orientation, size):
        font = ImageFont.truetype("serif.ttf", 16)
        horizontal_coord = ["a","b","c","d","e","f","g","h"]
        vertical_coord = ["8","7","6","5","4","3","2","1"]
        if (orientation == 'vertical'):
            legend = Image.new('RGB', (48,size), "white")
            draw = ImageDraw.Draw(legend)
            for count in range(1,9):
                draw.text((8, 32*(count*2)-32),vertical_coord[count-1],(0,0,0),font=font)
        else:
            legend = Image.new('RGB', (size,48), "white")
            draw = ImageDraw.Draw(legend)
            for count in range(1,9):
                draw.text((32*(count*2)-32, 8),horizontal_coord[count-1],(0,0,0),font=font)
        return legend

    def chess_position_using_font(self, fen, font_file, sq_size):
      font = ImageFont.truetype(font_file, sq_size)
      pieces = self.expand_fen(fen)
      board = self.draw_board(sq_size=(sq_size, sq_size))
      put_piece = ImageDraw.Draw(board).text
      unichr_pieces=dict(
        zip("KQRBNPkqrbnp", (chr(uc) for uc in range(0x2654, 0x2660))))
      
      def point(i, j):
        return i * sq_size, j * sq_size
      
      def not_blank(pt_pce):
        return pt_pce[1] != ' '
      
      def is_white_piece(piece):
        return piece.upper() == piece
      
      squares = (point(i, j) for j in range(8) for i in range(8))
      for square, piece in filter(not_blank, zip(squares, pieces)):
        if is_white_piece(piece):
          # Use the equivalent black piece, drawn white,
          # for the 'body' of the piece, so the background
          # square doesn't show through.
          filler = unichr_pieces[piece.lower()]
          put_piece(square, filler, fill='white', font=font)
        else:
          filler = unichr_pieces[piece.upper()]
          put_piece(square, filler, fill='white', font=font)
        put_piece(square, unichr_pieces[piece], fill='black', font=font)
      return board

    def boardGen(self, game, player, opponent, turn):
        full_board = Image.new('RGB', (548,548))
        chess_board = self.chess_position_using_font(game, "chess.ttf", 64)
        legend_vert = self.legend("vertical",548)
        legend_horz = self.legend("horizontal", 548)
        full_board.paste(chess_board, (0,0))
        full_board.paste(legend_vert, (512,0))
        full_board.paste(legend_horz, (0,512))
        full_board.save(settings.resourcedir + "images/chesstemp.png","PNG")
        story = "Chess game\n***" + str(player) + "*** as white \nVS\n ***" + str(opponent) + "*** as black\n__" + turn + "__ to play\n"
        return story


    # Process a turn, most of the logic is for the AI
    # but we'll also generate game messages for the
    # endgames and validate the moves
    def playchess(self,game,move,next_player,engine):
        board = chess.Board(game.fen)
        if (move == 'gg'):
            self.reset(game)
            return "Game over"
        try:
            board.push_san(move)
            update_board = True
        except:
            moves = str(board.legal_moves)
            raise UserError("Legal Moves: " + moves)
        if ((engine is not None) and (game.bot is True)):
            # The bot needs to take it's turn!
            engine.position(board)
            command = engine.go(depth=10)
            try:
                botmove = chess.Move.from_uci(str(command[0]))
                board.push(botmove)
            except:
                # The bot will not play if it is in checkmate
                # or the game is left with only the kings
                pass
        status = self.endgame(board,move,next_player,game)
        if update_board is True:
            botdata.chessinfo(game.playerid, game.opponentid, game.bot).fen = board.fen()
            if game.bot is False:
                botdata.chessinfo(game.playerid, game.opponentid, game.bot).turn = next_player
            else:
                botdata.chessinfo(game.playerid, game.opponentid, game.bot).turn = game.playerid
        return status

    def reset(self,game):
        botdata.chessinfo(game.playerid, game.opponentid, game.bot).fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    # End games on checkmate, and print a message if 
    # there is a computer draw by insufficient material
    def endgame(self,board,move,next_player,game):
        if board.is_checkmate() is  True:
            return "The game is in checkmate, " + str(next_player) + " has been defeated! Type __?chess @player gg__ to reset"
        if board.is_insufficient_material() is True:
            return "Play can continue, but the computer says it's a draw. Type __?chess @player gg__ to reset"
        return "The last move was " + str(move)

    @commands.command(pass_context=True, aliases=["chess"])
    async def challenge(self, ctx, user, move=None):
        engine = None
        if (len(ctx.message.mentions) is not 1):
            raise UserError("Please mention 1 user to challenge")
        if(ctx.message.author.id == ctx.message.mentions[0].id):
            raise UserError("You can't play against yourself")
        if(ctx.message.mentions[0].bot is True):
            try:
                engine = chess.uci.popen_engine(self.chessAI)
            except:
                raise UserError("No valid chess engine specified, so we can't play with a bot")
        game = botdata.chessinfo(ctx.message.author.name, ctx.message.mentions[0].name, ctx.message.mentions[0].bot)
        if (str(game.playerid) != str(ctx.message.author.name)):
            white = game.opponentid
            black = game.playerid
        else:
            white = game.playerid
            black = game.opponentid
        addendum = self.endgame(chess.Board(game.fen), ctx.message.mentions[0].name, None, game)
        if (move is not None):
            if (game.turn != ctx.message.author.name):
                await self.bot.say("It's not your turn!")
            else:
                addendum = self.playchess(game, move, ctx.message.mentions[0].name,engine)
                story = self.boardGen(game.fen, white, black, game.turn) + addendum
                chessImage = discord.File(settings.resource("images/chesstemp.png"))
                await ctx.send(file = chessImage, content=story)
        else:
            story = self.boardGen(game.fen, white, black, game.turn)
            chessImage = discord.File(settings.resource("images/chesstemp.png"))
            await ctx.send(file = chessImage, content=story)

def setup(bot):
    bot.add_cog(Chess(bot))
