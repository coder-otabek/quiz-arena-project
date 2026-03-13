import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

AUTO_ADVANCE_DELAY = 3  # sekund


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        kwargs = self.scope['url_route']['kwargs']
        self.game_pin  = kwargs['game_pin']
        self.role      = kwargs.get('role', 'player')
        self.player_id = kwargs.get('player_id', None)
        self.room      = f'game_{self.game_pin}'

        game_exists = await self.check_game_exists()
        if not game_exists:
            await self.close()
            return

        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()

        if self.role == 'player' and self.player_id:
            await self.set_player_channel(self.player_id, self.channel_name)

        await self.send_current_state()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room, self.channel_name)
        if self.role == 'player' and self.player_id:
            removed = await self.remove_player_if_waiting(self.player_id)
            if removed:
                # Lobby'ni yangilash — boshqalar ko'rsin
                count, players = await self.get_lobby_state()
                stats = await self.get_stats()
                await self.channel_layer.group_send(self.room, {
                    'type': 'lobby_update',
                    'count': count,
                    'players': players,
                    'stats': stats,
                })
            else:
                await self.clear_player_channel(self.player_id)

    async def receive(self, text_data):
        data   = json.loads(text_data)
        action = data.get('action')
        handler = {
            'start_game':    self.on_start_game,
            'next_question': self.on_next_question,
            'show_review':   self.on_show_review,
            'submit_answer': self.on_submit_answer,
            'player_ready':  self.on_player_ready,
        }.get(action)
        if handler:
            await handler(data)

    async def on_player_ready(self, data):
        count, players = await self.get_lobby_state()
        stats = await self.get_stats()
        await self.channel_layer.group_send(self.room, {
            'type': 'lobby_update', 'count': count,
            'players': players, 'stats': stats,
        })

    async def on_start_game(self, data):
        q = await self.get_question(0)
        if not q:
            return
        await self.set_game_status('question', 0)
        stats = await self.get_stats()
        await self.channel_layer.group_send(self.room, {
            'type': 'question_show', 'question': q, 'index': 0, 'stats': stats,
        })

    async def on_next_question(self, data):
        idx = data.get('index', 0) + 1
        q   = await self.get_question(idx)
        if q:
            await self.set_game_status('question', idx)
            stats = await self.get_stats()
            await self.channel_layer.group_send(self.room, {
                'type': 'question_show', 'question': q, 'index': idx, 'stats': stats,
            })
        else:
            await self.set_game_status('finished', idx)
            lb    = await self.get_leaderboard()
            stats = await self.get_stats()
            await self.channel_layer.group_send(self.room, {
                'type': 'game_end', 'leaderboard': lb, 'stats': stats,
            })

    async def on_show_review(self, data):
        idx          = data.get('index', 0)
        review       = await self.get_review_data(idx)
        lb           = await self.get_leaderboard()
        stats        = await self.get_stats()
        total_q      = await self.get_total_questions()
        player_stats = await self.get_player_stats()
        is_last      = (idx >= total_q - 1)

        await self.channel_layer.group_send(self.room, {
            'type': 'review_show', 'review': review, 'leaderboard': lb,
            'stats': stats, 'is_last': is_last, 'player_stats': player_stats,
        })

        if not is_last:
            # Server tomonida avtomatik keyingi savolga o'tish
            asyncio.ensure_future(self._auto_next(idx))

    async def on_submit_answer(self, data):
        pid     = data.get('player_id')
        aid     = data.get('answer_id')
        elapsed = data.get('elapsed', 0)
        result  = await self.save_answer(pid, aid, elapsed)
        await self.send(text_data=json.dumps({'action': 'answer_result', **result}))
        answered, total, counts = await self.get_answer_progress()
        stats        = await self.get_stats()
        player_stats = await self.get_player_stats()
        await self.channel_layer.group_send(self.room, {
            'type': 'answer_progress', 'answered': answered,
            'total': total, 'counts': counts, 'stats': stats,
            'player_stats': player_stats,
        })

    async def _auto_next(self, idx):
        """AUTO_ADVANCE_DELAY soniyadan keyin keyingi savolga o'tadi (server side)"""
        await asyncio.sleep(AUTO_ADVANCE_DELAY)
        current = await self.get_current_index()
        if current != idx:
            return  # allaqachon o'tib ketgan
        next_idx = idx + 1
        q = await self.get_question(next_idx)
        if q:
            await self.set_game_status('question', next_idx)
            stats        = await self.get_stats()
            player_stats = await self.get_player_stats()
            await self.channel_layer.group_send(self.room, {
                'type': 'question_show', 'question': q,
                'index': next_idx, 'stats': stats,
                'player_stats': player_stats,
            })
        else:
            await self.set_game_status('finished', next_idx)
            lb    = await self.get_leaderboard()
            stats = await self.get_stats()
            await self.channel_layer.group_send(self.room, {
                'type': 'game_end', 'leaderboard': lb, 'stats': stats,
            })

    async def lobby_update(self, event):
        await self.send(text_data=json.dumps({'action': 'lobby_update', **event}))

    async def question_show(self, event):
        if self.role == 'player':
            q = dict(event['question'])
            q['answers'] = [{'id': a['id'], 'text': a['text'], 'color': a['color']}
                            for a in q.get('answers', [])]
            await self.send(text_data=json.dumps({
                'action': 'question_show', 'question': q,
                'index': event['index'], 'stats': event.get('stats', {}),
            }))
        else:
            await self.send(text_data=json.dumps({'action': 'question_show', **event}))

    async def answer_progress(self, event):
        await self.send(text_data=json.dumps({'action': 'answer_progress', **event}))

    async def review_show(self, event):
        await self.send(text_data=json.dumps({'action': 'review_show', **event}))

    async def game_end(self, event):
        await self.send(text_data=json.dumps({'action': 'game_end', **event}))

    async def send_current_state(self):
        """Ulanayotgan foydalanuvchiga joriy game holatini yuboradi (refresh uchun)"""
        state = await self.get_game_state()
        if not state:
            return
        status = state['status']

        if status == 'waiting':
            count, players = await self.get_lobby_state()
            stats = await self.get_stats()
            await self.send(text_data=json.dumps({
                'action': 'lobby_update',
                'count': count, 'players': players, 'stats': stats,
            }))

        elif status == 'question':
            idx = state['current_question_index']
            q = await self.get_question(idx)
            stats = await self.get_stats()
            player_stats = await self.get_player_stats()
            if q:
                if self.role == 'player':
                    q_data = dict(q)
                    q_data['answers'] = [
                        {'id': a['id'], 'text': a['text'], 'color': a['color']}
                        for a in q_data.get('answers', [])
                    ]
                else:
                    q_data = q
                await self.send(text_data=json.dumps({
                    'action': 'question_show', 'question': q_data,
                    'index': idx, 'stats': stats, 'player_stats': player_stats,
                }))

        elif status == 'finished':
            lb = await self.get_leaderboard()
            stats = await self.get_stats()
            await self.send(text_data=json.dumps({
                'action': 'game_end', 'leaderboard': lb, 'stats': stats,
            }))

    @database_sync_to_async
    def set_player_channel(self, player_id, channel_name):
        from .models import Player
        Player.objects.filter(id=player_id).update(channel_name=channel_name)

    @database_sync_to_async
    def clear_player_channel(self, player_id):
        from .models import Player
        Player.objects.filter(id=player_id).update(channel_name='')

    @database_sync_to_async
    def remove_player_if_waiting(self, player_id):
        """Game 'waiting' holatida bo'lsa player'ni o'chiradi. O'chirildi → True"""
        from .models import Player, GameSession
        try:
            session = GameSession.objects.get(game_pin=self.game_pin)
            if session.status == 'waiting':
                Player.objects.filter(id=player_id, session=session).delete()
                return True
        except GameSession.DoesNotExist:
            pass
        return False

    @database_sync_to_async
    def check_game_exists(self):
        from .models import GameSession
        return GameSession.objects.filter(game_pin=self.game_pin).exists()

    @database_sync_to_async
    def get_game_state(self):
        from .models import GameSession
        try:
            s = GameSession.objects.get(game_pin=self.game_pin)
            return {'status': s.status, 'current_question_index': s.current_question_index}
        except GameSession.DoesNotExist:
            return None

    @database_sync_to_async
    def get_lobby_state(self):
        from .models import GameSession
        session = GameSession.objects.get(game_pin=self.game_pin)
        players = list(session.players.values('id', 'nickname', 'avatar'))
        return len(players), players

    @database_sync_to_async
    def get_question(self, index):
        from .models import GameSession
        session   = GameSession.objects.get(game_pin=self.game_pin)
        questions = list(session.quiz_set.questions.prefetch_related('answers').all())
        if index >= len(questions):
            return None
        q = questions[index]
        return {
            'id': q.id, 'text': q.text, 'time_limit': q.time_limit,
            'points': q.points, 'index': index, 'total': len(questions),
            'answers': [
                {'id': a.id, 'text': a.text, 'color': a.color, 'is_correct': a.is_correct}
                for a in q.answers.all()
            ],
        }

    @database_sync_to_async
    def set_game_status(self, status, index):
        from .models import GameSession
        GameSession.objects.filter(game_pin=self.game_pin).update(
            status=status, current_question_index=index,
        )

    @database_sync_to_async
    def save_answer(self, player_id, answer_id, elapsed):
        from .models import Player, Answer, PlayerAnswer, GameSession
        session  = GameSession.objects.get(game_pin=self.game_pin)
        player   = Player.objects.get(id=player_id)
        questions = list(session.quiz_set.questions.all())
        q        = questions[session.current_question_index]
        answer     = Answer.objects.filter(id=answer_id).first() if answer_id else None
        is_correct = bool(answer and answer.is_correct)
        pts = 0
        if is_correct:
            ratio = min(elapsed / q.time_limit, 1.0)
            pts   = int(q.points * (1 - ratio * 0.5))
        PlayerAnswer.objects.update_or_create(
            player=player, question=q,
            defaults=dict(answer=answer, is_correct=is_correct,
                          time_taken=elapsed, points_earned=pts)
        )
        player.score += pts
        player.save()
        return {
            'is_correct': is_correct, 'points_earned': pts,
            'total_score': player.score,
            'correct_answer': q.answers.filter(is_correct=True).values('id', 'text').first(),
        }

    @database_sync_to_async
    def get_answer_progress(self):
        from .models import GameSession, PlayerAnswer
        session   = GameSession.objects.get(game_pin=self.game_pin)
        questions = list(session.quiz_set.questions.all())
        if session.current_question_index < 0:
            return 0, 0, {}
        q        = questions[session.current_question_index]
        answered = PlayerAnswer.objects.filter(question=q, player__session=session).count()
        total    = session.players.count()
        counts   = {str(a.id): PlayerAnswer.objects.filter(
            question=q, answer=a, player__session=session).count()
            for a in q.answers.all()}
        return answered, total, counts

    @database_sync_to_async
    def get_review_data(self, index):
        from .models import GameSession, PlayerAnswer
        session   = GameSession.objects.get(game_pin=self.game_pin)
        questions = list(session.quiz_set.questions.prefetch_related('answers').all())
        q         = questions[index]
        result    = []
        for a in q.answers.all():
            cnt = PlayerAnswer.objects.filter(
                question=q, answer=a, player__session=session).count()
            result.append({'id': a.id, 'text': a.text, 'color': a.color,
                           'is_correct': a.is_correct, 'count': cnt})
        return {'question': q.text, 'answers': result}

    @database_sync_to_async
    def get_player_stats(self):
        """Har o'yinchi uchun: to'g'ri javoblar soni"""
        from .models import GameSession, PlayerAnswer
        session  = GameSession.objects.get(game_pin=self.game_pin)
        total_q  = session.quiz_set.questions.count()
        players  = session.players.all()
        result   = []
        for p in players:
            correct = PlayerAnswer.objects.filter(
                player=p, is_correct=True).count()
            result.append({
                'nickname': p.nickname,
                'avatar':   p.avatar,
                'correct':  correct,
                'score':    p.score,
            })
        # score bo'yicha tartiblash
        result.sort(key=lambda x: (-x['score'], x['nickname']))
        return {'players': result, 'total_q': total_q}

    @database_sync_to_async
    def get_current_index(self):
        from .models import GameSession
        session = GameSession.objects.get(game_pin=self.game_pin)
        return session.current_question_index

    @database_sync_to_async
    def get_total_questions(self):
        from .models import GameSession
        session = GameSession.objects.get(game_pin=self.game_pin)
        return session.quiz_set.questions.count()

    @database_sync_to_async
    def get_leaderboard(self):
        """Reyting: score DESC, keyin avg_time_taken ASC (teng ballda tezroq yuqorida)"""
        from .models import GameSession
        from django.db.models import Avg
        session = GameSession.objects.get(game_pin=self.game_pin)
        players = (session.players
                   .annotate(avg_time=Avg('answers__time_taken'))
                   .order_by('-score', 'avg_time'))
        return [{'nickname': p.nickname, 'avatar': p.avatar,
                 'score': p.score, 'avg_time': round(p.avg_time or 0, 2)}
                for p in players]

    @database_sync_to_async
    def get_stats(self):
        """Kirdi / Ishlayapti / Tugatdi statistikasi"""
        from .models import GameSession
        from django.db.models import Count
        session  = GameSession.objects.get(game_pin=self.game_pin)
        total_q  = session.quiz_set.questions.count()
        total_p  = session.players.count()
        finished = session.players.annotate(
            ac=Count('answers')).filter(ac__gte=total_q).count()
        playing  = session.players.annotate(
            ac=Count('answers')).filter(ac__gt=0, ac__lt=total_q).count()
        return {'joined': total_p, 'playing': playing, 'finished': finished}