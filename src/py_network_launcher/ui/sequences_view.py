"""Vue « Séquences » : liste à gauche, éditeur d'étapes à droite."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Optional

import flet as ft

from py_network_launcher.executor import OUTCOME_FAILED, OUTCOME_STOPPED, OUTCOME_SUCCESS
from py_network_launcher.models import (
    ACTION_LABELS,
    ACTION_TYPES,
    TRIGGER_APP_START,
    TRIGGER_LABELS,
    TRIGGER_MANUAL,
    TRIGGER_ONCE_PER_SESSION,
    ActionStep,
    LaunchSequence,
)
from py_network_launcher.service import RunState
from py_network_launcher.ui.step_card import STATE_DONE, STATE_FAILED, STATE_RUNNING, StepCard, StepCardHost
from py_network_launcher.ui.widgets import (
    ACTION_COLORS,
    ACTION_ICONS,
    COLOR_ERROR,
    COLOR_MUTED,
    COLOR_RUNNING,
    COLOR_SUCCESS,
    RADIUS,
    badge,
    dropdown,
    empty_state,
    muted_text,
    panel,
)
from py_network_launcher.windows import current_session_id

if TYPE_CHECKING:
    from py_network_launcher.ui.window import MainWindow


def _add_step_menu(on_add: Any, *, label: str = "Ajouter une étape") -> ft.PopupMenuButton:
    return ft.PopupMenuButton(
        tooltip="",
        menu_position=ft.PopupMenuPosition.UNDER,
        content=ft.Container(
            bgcolor=ft.Colors.SECONDARY_CONTAINER,
            border_radius=20,
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            content=ft.Row(
                tight=True,
                spacing=6,
                controls=[
                    ft.Icon(ft.Icons.ADD_ROUNDED, size=18, color=ft.Colors.ON_SECONDARY_CONTAINER),
                    ft.Text(label, size=13, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SECONDARY_CONTAINER),
                ],
            ),
        ),
        items=[
            ft.PopupMenuItem(
                content=ft.Row(
                    spacing=10,
                    controls=[ft.Icon(ACTION_ICONS[action_type], size=18, color=ACTION_COLORS[action_type]), ft.Text(ACTION_LABELS[action_type])],
                ),
                on_click=lambda _, current=action_type: on_add(current),
            )
            for action_type in ACTION_TYPES
        ],
    )


def _format_run_status(state: Optional[RunState]) -> tuple[str, str]:
    if state is None:
        return "Jamais lancée depuis l'ouverture de l'application", COLOR_MUTED
    if state.is_running:
        return f"En cours ({state.source})", COLOR_RUNNING
    at = time.strftime("%H:%M", time.localtime(state.finished_at)) if state.finished_at else ""
    if state.status == OUTCOME_SUCCESS:
        return f"Terminée avec succès à {at}", COLOR_SUCCESS
    if state.status == OUTCOME_STOPPED:
        return f"Arrêtée à {at}", ft.Colors.AMBER_200
    return f"Échec à {at} : {state.error}", COLOR_ERROR


class SequencesView:
    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self.selected_id: Optional[str] = window.config.sequences[0].id if window.config.sequences else None
        self._expanded_step_ids: set[str] = set()
        self._cards: dict[str, StepCard] = {}
        self._cards_sequence_id: Optional[str] = None

        self._list = ft.ListView(spacing=6, expand=True, padding=ft.Padding.only(right=4))
        self._editor = ft.Container(expand=True)
        self.control = ft.Row(
            expand=True,
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                panel(
                    title="Séquences",
                    width=300,
                    expand=False,
                    actions=[ft.IconButton(icon=ft.Icons.ADD_ROUNDED, tooltip="Nouvelle séquence", on_click=lambda _: self.add_sequence())],
                    content=self._list,
                ),
                ft.Container(expand=True, content=self._editor),
            ],
        )

        # Contrôles persistants de l'éditeur (jamais recréés pendant la saisie).
        self._name_field = ft.TextField(
            label="Nom de la séquence",
            dense=True,
            border_radius=10,
            expand=True,
            text_size=16,
            on_change=self._on_name_change,
        )
        self._trigger_dropdown = dropdown("Déclenchement automatique", None, list(TRIGGER_LABELS.items()), on_select=self._on_trigger_change, width=330)
        self._run_button = ft.FilledButton(on_click=lambda _: self.toggle_selected_run())
        self._run_status = ft.Text(size=12, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, expand=True)
        self._steps_title = ft.Text(size=15, weight=ft.FontWeight.W_600)
        self._expand_all_button = ft.IconButton(on_click=lambda _: self._toggle_all())
        self._steps_list = ft.ReorderableListView(
            expand=True,
            show_default_drag_handles=False,
            on_reorder=self._on_reorder,
            padding=ft.Padding.only(right=6),
        )
        self._steps_container = ft.Container(expand=True)
        self._editor_column = ft.Column(
            expand=True,
            spacing=12,
            controls=[
                ft.Container(
                    bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                    border_radius=RADIUS,
                    padding=16,
                    content=ft.Column(
                        spacing=14,
                        controls=[
                            ft.Row(
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    self._name_field,
                                    self._run_button,
                                    ft.PopupMenuButton(
                                        icon=ft.Icons.MORE_VERT,
                                        tooltip="Plus d'actions",
                                        items=[
                                            ft.PopupMenuItem(
                                                content="Dupliquer la séquence", icon=ft.Icons.CONTENT_COPY, on_click=lambda _: self.duplicate_selected()
                                            ),
                                            ft.PopupMenuItem(
                                                content="Supprimer la séquence", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda _: self.confirm_delete_selected()
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=16,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[self._trigger_dropdown, self._run_status],
                            ),
                        ],
                    ),
                ),
                ft.Container(
                    expand=True,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                    border_radius=RADIUS,
                    padding=ft.Padding.only(left=12, right=10, top=12, bottom=4),
                    content=ft.Column(
                        expand=True,
                        spacing=10,
                        controls=[
                            ft.Row(
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(content=self._steps_title, expand=True, padding=ft.Padding.only(left=4)),
                                    self._expand_all_button,
                                    _add_step_menu(self.add_step),
                                ],
                            ),
                            self._steps_container,
                        ],
                    ),
                ),
            ],
        )
        self.refresh_list()
        self.show_selected()

    # --- Accès ----------------------------------------------------------------------------

    @property
    def config(self):
        return self.window.config

    def selected(self) -> Optional[LaunchSequence]:
        return self.config.find_sequence(self.selected_id) if self.selected_id else None

    def _other_sequences(self) -> list[LaunchSequence]:
        return [item for item in self.config.sequences if item.id != self.selected_id]

    # --- Liste ----------------------------------------------------------------------------

    def refresh_list(self) -> None:
        if not self.config.sequences:
            self._list.controls = [
                empty_state(
                    icon=ft.Icons.PLAYLIST_ADD,
                    title="Aucune séquence",
                    message="Une séquence enchaîne des actions : lancer des applis, appeler un webhook, réveiller un PC…",
                    action=ft.FilledTonalButton("Créer une séquence", icon=ft.Icons.ADD_ROUNDED, on_click=lambda _: self.add_sequence()),
                )
            ]
            return
        self._list.controls = [self._sequence_tile(sequence) for sequence in self.config.sequences]

    def _sequence_tile(self, sequence: LaunchSequence) -> ft.Control:
        selected = sequence.id == self.selected_id
        state = self.window.service.run_state(sequence.id)
        status_icon: Optional[ft.Control] = None
        if state is not None and state.is_running:
            status_icon = ft.ProgressRing(width=16, height=16, stroke_width=2, color=COLOR_RUNNING, tooltip="En cours")
        elif state is not None and state.status == OUTCOME_FAILED:
            status_icon = ft.Icon(ft.Icons.ERROR, size=18, color=COLOR_ERROR, tooltip=state.error or "Échec")
        elif state is not None and state.status == OUTCOME_SUCCESS:
            status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=18, color=COLOR_SUCCESS, tooltip="Dernière exécution réussie")
        badges: list[ft.Control] = []
        if sequence.trigger == TRIGGER_APP_START:
            badges.append(badge("Au démarrage", color=ft.Colors.GREEN_300, icon=ft.Icons.ROCKET_LAUNCH_OUTLINED))
        elif sequence.trigger == TRIGGER_ONCE_PER_SESSION:
            badges.append(badge("1× par session", color=ft.Colors.AMBER_300, icon=ft.Icons.ROCKET_LAUNCH_OUTLINED))
        enabled_steps = sum(1 for step in sequence.steps if step.enabled)
        count = f"{enabled_steps} étape{'s' if enabled_steps > 1 else ''}"
        return ft.Container(
            border_radius=12,
            ink=True,
            bgcolor=ft.Colors.SECONDARY_CONTAINER if selected else ft.Colors.SURFACE_CONTAINER,
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            on_click=lambda _, sid=sequence.id: self.select(sid),
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(
                        expand=True,
                        spacing=4,
                        controls=[
                            ft.Text(sequence.name, size=14, weight=ft.FontWeight.W_600, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Row(spacing=6, wrap=True, controls=[muted_text(count), *badges]),
                        ],
                    ),
                    *([status_icon] if status_icon is not None else []),
                    ft.IconButton(
                        icon=ft.Icons.STOP_ROUNDED if state is not None and state.is_running else ft.Icons.PLAY_ARROW_ROUNDED,
                        icon_color=COLOR_RUNNING if state is not None and state.is_running else ft.Colors.PRIMARY,
                        tooltip="Arrêter" if state is not None and state.is_running else "Lancer",
                        on_click=lambda _, sid=sequence.id: self.window.toggle_run(sid),
                    ),
                ],
            ),
        )

    def select(self, sequence_id: str) -> None:
        if sequence_id == self.selected_id:
            return
        self.window.flush_pending_save()
        self.selected_id = sequence_id
        self.refresh_list()
        self.show_selected()

    # --- Éditeur --------------------------------------------------------------------------

    def show_selected(self) -> None:
        sequence = self.selected()
        if sequence is None:
            self._cards.clear()
            self._cards_sequence_id = None
            self._editor.content = panel(
                title="Éditeur",
                content=empty_state(
                    icon=ft.Icons.EDIT_NOTE,
                    title="Aucune séquence sélectionnée",
                    message="Crée une séquence ou sélectionne-en une dans la liste pour modifier ses étapes.",
                ),
            )
            return
        self._name_field.value = sequence.name
        self._name_field.error = None
        self._trigger_dropdown.value = sequence.trigger
        self._editor.content = self._editor_column
        self._rebuild_steps()
        self.refresh_run_state()

    def _host(self, sequence: LaunchSequence) -> StepCardHost:
        return StepCardHost(
            sequence=sequence,
            peers=self.window.service.peers,
            other_sequences=self._other_sequences,
            on_changed=lambda _step: self._on_step_changed(),
            on_toggle=self._toggle_step,
            on_test=self.window.test_step,
            on_delete=self.delete_step,
            on_duplicate=self.duplicate_step,
            on_move=self.move_step,
            pick_file=self.window.pick_file,
            pick_folder=self.window.pick_folder,
        )

    def _rebuild_steps(self) -> None:
        sequence = self.selected()
        if sequence is None:
            return
        host = self._host(sequence)
        count = len(sequence.steps)
        self._cards = {step.id: StepCard(step, index, count, host, expanded=step.id in self._expanded_step_ids) for index, step in enumerate(sequence.steps)}
        self._cards_sequence_id = sequence.id
        self._steps_list.controls = [card.control for card in self._cards.values()]
        if sequence.steps:
            self._steps_container.content = self._steps_list
        else:
            self._steps_container.content = empty_state(
                icon=ft.Icons.ADD_TASK,
                title="Aucune étape",
                message="Ajoute une première action. Tu pourras ensuite les réordonner par glisser-déposer.",
                action=_add_step_menu(self.add_step, label="Ajouter la première étape"),
            )
        self._refresh_steps_header()

    def _refresh_steps_header(self) -> None:
        sequence = self.selected()
        count = len(sequence.steps) if sequence is not None else 0
        self._steps_title.value = f"Étapes ({count})" if count else "Étapes"
        all_expanded = count > 0 and all(step.id in self._expanded_step_ids for step in sequence.steps)  # type: ignore[union-attr]
        self._expand_all_button.icon = ft.Icons.UNFOLD_LESS if all_expanded else ft.Icons.UNFOLD_MORE
        self._expand_all_button.tooltip = "Tout replier" if all_expanded else "Tout déplier"
        self._expand_all_button.visible = count > 1

    def refresh_run_state(self) -> None:
        """Met à jour les indicateurs d'exécution sans reconstruire l'éditeur."""
        sequence = self.selected()
        if sequence is None:
            return
        state = self.window.service.run_state(sequence.id)
        running = state is not None and state.is_running
        self._run_button.content = "Arrêter" if running else "Lancer"
        self._run_button.icon = ft.Icons.STOP_ROUNDED if running else ft.Icons.PLAY_ARROW_ROUNDED
        self._run_button.style = ft.ButtonStyle(bgcolor=ft.Colors.AMBER_700) if running else None
        self._run_status.value, self._run_status.color = _format_run_status(state)
        self._run_status.tooltip = self._run_status.value
        for step_id, card in self._cards.items():
            if state is None:
                card.set_run_state(None)
            elif step_id == state.active_step_id:
                card.set_run_state(STATE_RUNNING)
            elif step_id in state.failed_steps:
                card.set_run_state(STATE_FAILED, state.failed_steps[step_id])
            elif step_id in state.done_step_ids:
                card.set_run_state(STATE_DONE)
            else:
                card.set_run_state(None)

    def refresh_dynamic_options(self) -> None:
        for card in self._cards.values():
            card.refresh_dynamic_options()

    # --- Actions sur les séquences --------------------------------------------------------

    def toggle_selected_run(self) -> None:
        if self.selected_id:
            self.window.toggle_run(self.selected_id)

    def add_sequence(self) -> None:
        sequence = LaunchSequence(name=self._unique_name("Nouvelle séquence"))
        self.config.sequences.append(sequence)
        self.selected_id = sequence.id
        self._after_sequences_changed()
        self.window.notify("Séquence créée")

    def duplicate_selected(self) -> None:
        sequence = self.selected()
        if sequence is None:
            return
        copy = sequence.clone(new_identity=True)
        copy.name = self._unique_name(f"{sequence.name} (copie)")
        copy.trigger = TRIGGER_MANUAL  # éviter qu'une copie se lance automatiquement en double
        index = self.config.sequences.index(sequence)
        self.config.sequences.insert(index + 1, copy)
        self.selected_id = copy.id
        self._after_sequences_changed()
        self.window.notify(f"« {copy.name} » créée")

    def confirm_delete_selected(self) -> None:
        sequence = self.selected()
        if sequence is None:
            return
        users = self.config.sequences_referencing(sequence.id)
        message = f"La séquence « {sequence.name} » et ses {len(sequence.steps)} étape(s) seront supprimées définitivement."
        if users:
            message += "\n\nElle est appelée par : " + ", ".join(f"« {item.name} »" for item in users) + ". Ces étapes ne fonctionneront plus."
        self.window.confirm(
            title="Supprimer la séquence ?",
            message=message,
            confirm_label="Supprimer",
            on_confirm=lambda: self._delete_sequence(sequence.id),
            destructive=True,
        )

    def _delete_sequence(self, sequence_id: str) -> None:
        sequence = self.config.find_sequence(sequence_id)
        if sequence is None:
            return
        self.window.service.stop_sequence(sequence_id)
        index = self.config.sequences.index(sequence)
        self.config.sequences.remove(sequence)
        self.window.service.clear_run_state(sequence_id)
        remaining = self.config.sequences
        self.selected_id = remaining[min(index, len(remaining) - 1)].id if remaining else None
        self._after_sequences_changed()
        self.window.notify(f"« {sequence.name} » supprimée")

    def _after_sequences_changed(self) -> None:
        self.window.save_now()
        self.refresh_list()
        self.show_selected()
        self.window.sequences_changed()

    def _unique_name(self, base: str) -> str:
        names = {item.name for item in self.config.sequences}
        if base not in names:
            return base
        index = 2
        while f"{base} {index}" in names:
            index += 1
        return f"{base} {index}"

    def _on_name_change(self, event: Any) -> None:
        sequence = self.selected()
        if sequence is None:
            return
        name = str(event.control.value or "").strip()
        self._name_field.error = None if name else "Le nom ne peut pas être vide"
        if not name:
            return
        sequence.name = name
        self.window.save_soon()
        self.refresh_list()
        self.window.sequences_changed()

    def _on_trigger_change(self, event: Any) -> None:
        sequence = self.selected()
        if sequence is None:
            return
        sequence.trigger = str(event.control.value or "")
        if sequence.trigger == TRIGGER_ONCE_PER_SESSION:
            # Ne pas relancer dans la session courante une séquence qu'on vient de configurer.
            sequence.last_session_id = current_session_id()
        self.window.save_now()
        self.refresh_list()

    # --- Actions sur les étapes -----------------------------------------------------------

    def add_step(self, action_type: str) -> None:
        sequence = self.selected()
        if sequence is None:
            return
        step = ActionStep(action_type=action_type)
        sequence.steps.append(step)
        self._expanded_step_ids.add(step.id)
        self._after_steps_changed()
        if len(sequence.steps) > 3:
            self.window.page.run_task(self._scroll_to_end)

    async def _scroll_to_end(self) -> None:
        await self._steps_list.scroll_to(offset=-1, duration=300)

    def duplicate_step(self, step: ActionStep) -> None:
        sequence = self.selected()
        if sequence is None:
            return
        copy = step.clone(new_identity=True)
        sequence.steps.insert(sequence.index_of(step.id) + 1, copy)
        if step.id in self._expanded_step_ids:
            self._expanded_step_ids.add(copy.id)
        self._after_steps_changed()

    def delete_step(self, step: ActionStep) -> None:
        sequence = self.selected()
        if sequence is None:
            return
        index = sequence.index_of(step.id)
        if index < 0:
            return
        sequence.steps.pop(index)
        self._after_steps_changed()

        def undo() -> None:
            if sequence.find_step(step.id) is None:
                sequence.steps.insert(min(index, len(sequence.steps)), step)
                self._after_steps_changed()

        self.window.notify(f"Étape « {step.label} » supprimée", action_label="Annuler", on_action=undo)

    def move_step(self, step: ActionStep, delta: int) -> None:
        sequence = self.selected()
        if sequence is None:
            return
        index = sequence.index_of(step.id)
        target = index + delta
        if index < 0 or not 0 <= target < len(sequence.steps):
            return
        self._move(sequence, index, target)

    def _on_reorder(self, event: ft.OnReorderEvent) -> None:
        sequence = self.selected()
        if sequence is None or event.old_index is None or event.new_index is None:
            return
        target = event.new_index
        if target > event.old_index and target >= len(sequence.steps):
            target = len(sequence.steps) - 1
        self._move(sequence, event.old_index, target)

    def _move(self, sequence: LaunchSequence, old_index: int, new_index: int) -> None:
        if old_index == new_index:
            return
        sequence.steps.insert(new_index, sequence.steps.pop(old_index))
        controls = self._steps_list.controls
        controls.insert(new_index, controls.pop(old_index))
        count = len(sequence.steps)
        for index, step in enumerate(sequence.steps):
            self._cards[step.id].set_index(index, count)
        self.window.save_now()

    def _toggle_step(self, step: ActionStep) -> None:
        card = self._cards.get(step.id)
        if card is None:
            return
        if step.id in self._expanded_step_ids:
            self._expanded_step_ids.discard(step.id)
        else:
            self._expanded_step_ids.add(step.id)
        card.set_expanded(step.id in self._expanded_step_ids)
        self._refresh_steps_header()

    def _toggle_all(self) -> None:
        sequence = self.selected()
        if sequence is None:
            return
        ids = {step.id for step in sequence.steps}
        expand = not ids <= self._expanded_step_ids
        if expand:
            self._expanded_step_ids |= ids
        else:
            self._expanded_step_ids -= ids
        for card in self._cards.values():
            card.set_expanded(expand)
        self._refresh_steps_header()

    def _on_step_changed(self) -> None:
        self.window.save_soon()
        self.refresh_list()

    def _after_steps_changed(self) -> None:
        self.window.save_now()
        self._rebuild_steps()
        self.refresh_run_state()
        self.refresh_list()
