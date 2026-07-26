"""The application service: the one place a mutation touches the tree.

Every method that changes ``sdlc/`` does three things atomically-in-spirit:

1. applies the law (allocate id → template → ``write_new`` / entomb / PRD edit);
2. records a row in the audit ledger (who / what / when / hashes);
3. appends an event to the session transcript.

The MCP server (``server.py``) is a thin wrapper over these methods; tests drive
this class directly against a temp tree, no transport involved.
"""

from __future__ import annotations

from datetime import date

from .audit import db as audit_db
from .audit import ledger
from .config import Config, load_config
from .integrations import factory as integrations_factory
from .law import artifacts
from .law import entomb as entomb_mod
from .law import frontmatter, ids, prd
from .law import templates
from .law import validate as validate_mod
from .transcript.session import SessionLog, new_session_id


class SdlcService:
    def __init__(self, cfg: Config | None = None, *, conn=None, session_id: str | None = None):
        self.cfg = cfg or load_config()
        self.conn = conn or audit_db.connect(self.cfg.audit_db)
        self.session_id = session_id or new_session_id()
        self.log = SessionLog(self.cfg.transcript_dir, self.session_id)
        ledger.start_session(
            self.conn,
            session_id=self.session_id,
            human=self.cfg.actor_human,
            title=None,
        )

    # ----------------------------------------------------------------- utils
    @property
    def root(self):
        return self.cfg.sdlc_root

    def _today(self) -> str:
        return date.today().isoformat()

    def _rel(self, path) -> str:
        return str(path.relative_to(self.root))

    def _record(self, **kw) -> int:
        return ledger.record(
            self.conn,
            session_id=self.session_id,
            actor_human=self.cfg.actor_human,
            actor_agent=self.cfg.actor_agent,
            **kw,
        )

    def _cite(self, from_type: str, target_id: str) -> str:
        ref = ids.resolve(self.root, target_id)
        if ref is None:
            raise ValueError(f"cannot cite unknown id {target_id}")
        from_dir = templates.link_dir(self.root, from_type)
        return frontmatter.citation_link(target_id, from_dir / "_.md", ref.path)

    def _cite_requirement(self, from_type: str, rid: str) -> str:
        from_dir = templates.link_dir(self.root, from_type)
        return frontmatter.citation_link(rid, from_dir / "_.md", prd.prd_path(self.root))

    def _commit_new(
        self, *, artifact_type, new_id, rel, content, action, summary, supersede_of=None
    ) -> dict:
        if supersede_of:
            content = (
                f"<!-- supersedes {supersede_of} -->\n"
                f"> supersedes {supersede_of}\n\n" + content
            )
        artifacts.write_new(self.root, rel, content)
        self._record(
            action=action,
            artifact_type=artifact_type,
            artifact_id=new_id,
            path=rel,
            summary=summary,
            new_content=content,
            extra={"supersedes": supersede_of} if supersede_of else None,
        )
        self.log.append(
            "artifact_created",
            id=new_id,
            type=artifact_type,
            path=rel,
            action=action,
            supersedes=supersede_of,
        )
        result = {"id": new_id, "path": rel}
        if supersede_of:
            old_ref = ids.resolve(self.root, supersede_of)
            old_content = old_ref.path.read_text(encoding="utf-8") if old_ref else None
            obsolete = entomb_mod.entomb(
                self.root,
                supersede_of,
                when=self._today(),
                why=f"superseded by {new_id}: {summary}",
                superseded_by=new_id,
            )
            self._record(
                action="entomb",
                artifact_type=ids.id_type(supersede_of),
                artifact_id=supersede_of,
                path=self._rel(obsolete),
                summary=f"superseded by {new_id}",
                prev_content=old_content,
            )
            self.log.append(
                "artifact_entombed", id=supersede_of, superseded_by=new_id
            )
            result["superseded"] = supersede_of
            result["obsolete_path"] = self._rel(obsolete)
        return result

    # ----------------------------------------------------------------- reads
    def allocate_id(self, artifact_type: str) -> str:
        return ids.allocate(self.root, artifact_type)

    def resolve_id(self, artifact_id: str) -> dict:
        ref = ids.resolve(self.root, artifact_id)
        if ref is None:
            return {"id": artifact_id, "exists": False}
        return {
            "id": artifact_id,
            "exists": True,
            "path": self._rel(ref.path),
            "is_obsolete": ref.is_obsolete,
        }

    def read_artifact(self, artifact_id: str) -> str:
        return artifacts.read(self.root, artifact_id)

    def list_artifacts(self, artifact_type: str) -> list[dict]:
        return [
            {"id": r.id, "path": self._rel(r.path), "is_obsolete": r.is_obsolete}
            for r in artifacts.list_type(self.root, artifact_type)
        ]

    def read_prd(self) -> str:
        return prd.read(self.root)

    def validate(self) -> dict:
        return validate_mod.validate_tree(self.root).as_dict()

    def audit_history(self, **filters) -> list[dict]:
        return [dict(r) for r in ledger.history(self.conn, **filters)]

    def transcript_read(self) -> list[dict]:
        return self.log.read()

    def session_note(self, text: str) -> dict:
        self.log.append("note", text=text)
        self._record(action="note", summary=text)
        return {"session_id": self.session_id}

    # --------------------------------------------------------------- business
    def create_business_task(
        self,
        *,
        name,
        requirements=None,
        title=None,
        kind="planning",
        severity=None,
        raw_note="нет.",
        current_state="TBD.",
        what_to_do="TBD.",
        acceptance=None,
        description="TBD.",
        open_questions="Нет.",
        surfaced_by=None,
        supersede_of=None,
    ) -> dict:
        bt_id = self.allocate_id("BT")
        req_links = [self._cite_requirement("BT", r) for r in (requirements or [])]
        surfaced_link = self._cite("BT", surfaced_by) if surfaced_by else None
        if kind == "planning":
            rel, content = templates.business_task_planning(
                bt_id=bt_id,
                name=name,
                title=title,
                requirement_links=req_links,
                raw_note=raw_note,
                current_state=current_state,
                what_to_do=what_to_do,
                acceptance=acceptance,
                open_questions=open_questions,
                surfaced_by_link=surfaced_link,
            )
        else:
            rel, content = templates.business_task_observation(
                bt_id=bt_id,
                severity=severity or "INFO",
                name=name,
                title=title,
                requirement_links=req_links,
                raw_note=raw_note,
                description=description,
                acceptance=acceptance,
                open_questions=open_questions,
            )
        return self._commit_new(
            artifact_type="BT",
            new_id=bt_id,
            rel=rel,
            content=content,
            action="create_business_task",
            summary=title or name,
            supersede_of=supersede_of,
        )

    # ------------------------------------------------------------------ specs
    def create_module(
        self, *, name, derived_from_bt, purpose="TBD.", composition="TBD.",
        boundary="TBD.", supersede_of=None,
    ) -> dict:
        mod_id = self.allocate_id("MOD")
        rel, content = templates.module(
            mod_id=mod_id,
            name=name,
            derived_from_link=self._cite("MOD", derived_from_bt),
            purpose=purpose,
            composition=composition,
            boundary=boundary,
        )
        return self._commit_new(
            artifact_type="MOD", new_id=mod_id, rel=rel, content=content,
            action="create_module", summary=name, supersede_of=supersede_of,
        )

    def create_actor(
        self, *, name, module, title, identity="TBD.", goals="TBD.",
        permissions="TBD.", interacts=None, supersede_of=None,
    ) -> dict:
        actor_id = self.allocate_id("ACTOR")
        interacts_links = [self._cite("ACTOR", x) for x in (interacts or [])] or None
        rel, content = templates.actor(
            actor_id=actor_id, name=name, module=module, title=title,
            identity=identity, goals=goals, permissions=permissions,
            interacts_links=interacts_links,
        )
        return self._commit_new(
            artifact_type="ACTOR", new_id=actor_id, rel=rel, content=content,
            action="create_actor", summary=title, supersede_of=supersede_of,
        )

    def create_entity(
        self, *, name, module, title, owning_module, description="TBD.",
        fields=None, source_rows=None, supersede_of=None,
    ) -> dict:
        ent_id = self.allocate_id("ENT")
        rel, content = templates.entity(
            ent_id=ent_id, name=name, module=module, title=title,
            owning_module_link=self._cite("ENT", owning_module),
            description=description, fields=fields, source_rows=source_rows,
        )
        return self._commit_new(
            artifact_type="ENT", new_id=ent_id, rel=rel, content=content,
            action="create_entity", summary=title, supersede_of=supersede_of,
        )

    def create_event(
        self, *, name, module, title, initiator, entities, trigger="TBD.",
        effect="TBD.", source="TBD.", supersede_of=None,
    ) -> dict:
        evt_id = self.allocate_id("EVT")
        rel, content = templates.event(
            evt_id=evt_id, name=name, module=module, title=title,
            initiator_link=self._cite("EVT", initiator),
            entity_links=[self._cite("EVT", e) for e in entities],
            trigger=trigger, effect=effect, source=source,
        )
        return self._commit_new(
            artifact_type="EVT", new_id=evt_id, rel=rel, content=content,
            action="create_event", summary=title, supersede_of=supersede_of,
        )

    def create_use_case(
        self, *, actor_id, evt_id, ent_id, crud, outcome, module, title,
        purpose="TBD.", current_main="TBD.", current_alt="Нет.",
        related_entities=None, business_rules="Нет.",
        target="Не отличается от CURRENT.", tbd="Нет.", tech_deps="TBD.",
        acceptance=None, tests="TBD — теста нет.", open_questions="Нет.",
        supersede_of=None,
    ) -> dict:
        uc_id = self.allocate_id("UC")
        related_links = [self._cite("UC", e) for e in (related_entities or [])] or None
        rel, content = templates.use_case(
            uc_id=uc_id, actor_id=actor_id, evt_id=evt_id, ent_id=ent_id,
            crud=crud, outcome=outcome, module=module, title=title,
            actor_link=self._cite("UC", actor_id),
            event_link=self._cite("UC", evt_id),
            entity_links=[self._cite("UC", ent_id)],
            purpose=purpose, current_main=current_main, current_alt=current_alt,
            related_entity_links=related_links, business_rules=business_rules,
            target=target, tbd=tbd, tech_deps=tech_deps, acceptance=acceptance,
            tests=tests, open_questions=open_questions,
        )
        return self._commit_new(
            artifact_type="UC", new_id=uc_id, rel=rel, content=content,
            action="create_use_case", summary=title, supersede_of=supersede_of,
        )

    # ------------------------------------------------------------------- misc
    def entomb_artifact(self, artifact_id: str, *, why: str, superseded_by=None) -> dict:
        ref = ids.resolve(self.root, artifact_id)
        old_content = ref.path.read_text(encoding="utf-8") if ref else None
        obsolete = entomb_mod.entomb(
            self.root, artifact_id, when=self._today(), why=why, superseded_by=superseded_by
        )
        rel = self._rel(obsolete)
        self._record(
            action="entomb",
            artifact_type=ids.id_type(artifact_id),
            artifact_id=artifact_id,
            path=rel,
            summary=why,
            prev_content=old_content,
            extra={"superseded_by": superseded_by} if superseded_by else None,
        )
        self.log.append(
            "artifact_entombed", id=artifact_id, why=why, superseded_by=superseded_by
        )
        return {"id": artifact_id, "obsolete_path": rel, "superseded_by": superseded_by}

    # -------------------------------------------------------------------- PRD
    def prd_add_requirement(self, text: str) -> dict:
        rid = prd.next_requirement_id(self.root)
        old = prd.read(self.root)
        new = prd.insert_requirement(old, rid, text)
        prd.snapshot_and_write(self.root, new, date=self._today(), why=f"add {rid}")
        self._record(
            action="prd_add_requirement", artifact_type="PRD", artifact_id=rid,
            path=prd.PRD_REL, summary=text, prev_content=old, new_content=new,
        )
        self.log.append("prd_requirement_added", id=rid, text=text)
        return {"id": rid}

    def prd_deprecate_requirement(self, rid: str, replaced_by: str) -> dict:
        old = prd.read(self.root)
        new = prd.deprecate_requirement(old, rid, replaced_by)
        prd.snapshot_and_write(
            self.root, new, date=self._today(), why=f"deprecate {rid} -> {replaced_by}"
        )
        self._record(
            action="prd_deprecate_requirement", artifact_type="PRD", artifact_id=rid,
            path=prd.PRD_REL, summary=f"{rid} -> {replaced_by}",
            prev_content=old, new_content=new,
        )
        self.log.append("prd_requirement_deprecated", id=rid, replaced_by=replaced_by)
        return {"id": rid, "replaced_by": replaced_by}

    def prd_propose_edit(self, new_text: str, why: str) -> dict:
        old = prd.read(self.root)
        hist, _ = prd.snapshot_and_write(self.root, new_text, date=self._today(), why=why)
        self._record(
            action="prd_edit", artifact_type="PRD", path=prd.PRD_REL,
            summary=why, prev_content=old, new_content=new_text,
        )
        self.log.append("prd_edited", why=why, history=self._rel(hist))
        return {"history": self._rel(hist)}

    # ----------------------------------------------------------- integrations
    def _integrations(self):
        return integrations_factory.build(self.cfg)

    def open_pull_request(self, *, title, body="", base="develop", head=None) -> dict:
        repo = str(self.cfg.app_repo) if self.cfg.app_repo else None
        res = self._integrations().git.open_pull_request(
            repo=repo, base=base, head=head, title=title, body=body
        )
        self._record(
            action="open_pull_request",
            summary=title,
            extra={"url": res.url, "branch": res.branch, "used_fake": res.used_fake},
        )
        self.log.append(
            "pull_request", title=title, url=res.url, branch=res.branch,
            used_fake=res.used_fake,
        )
        return {
            "ok": res.ok, "url": res.url, "branch": res.branch,
            "detail": res.detail, "used_fake": res.used_fake,
        }

    def build_and_deliver_apk(self, *, flavor="prod", caption=None) -> dict:
        repo = str(self.cfg.app_repo) if self.cfg.app_repo else None
        ig = self._integrations()
        build = ig.apk.build(repo=repo, flavor=flavor)
        delivery = None
        if build.ok and build.apk_path:
            delivery = ig.telegram.send_document(
                path=build.apk_path, caption=caption or f"APK ({flavor})"
            )
        self._record(
            action="build_and_deliver_apk",
            summary=f"apk {flavor}",
            extra={
                "apk_path": build.apk_path,
                "build_used_fake": build.used_fake,
                "delivered": bool(delivery and delivery.ok),
                "delivery_used_fake": delivery.used_fake if delivery else None,
            },
        )
        self.log.append(
            "apk_build", flavor=flavor, apk=build.apk_path,
            delivered=bool(delivery and delivery.ok), build_used_fake=build.used_fake,
        )
        return {
            "build": {
                "ok": build.ok, "apk_path": build.apk_path,
                "used_fake": build.used_fake, "detail": build.detail,
            },
            "delivery": (
                {"ok": delivery.ok, "used_fake": delivery.used_fake, "detail": delivery.detail}
                if delivery
                else None
            ),
        }
