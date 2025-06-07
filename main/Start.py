from dotenv import load_dotenv
import matplotlib

from Note_bot.main.NoteBot import NoteBot

matplotlib.use('Agg')

load_dotenv()

if __name__ == "__main__":
    note_bot = NoteBot()
    note_bot.run()
